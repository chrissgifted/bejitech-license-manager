"""Bejitech License Manager, web version (FastAPI).

The web pages are a thin layer over the same services the desktop app uses: every business
rule (stock, allocation, cancellations, delivery notes, audit) stays in bejitech.services.

Sign-in has two steps: password, then a 6-digit code from an authenticator app. The login
cookie is signed, HTTP-only, HTTPS-only and expires after inactivity.
"""
from __future__ import annotations

import hmac
import logging
import secrets
import time
from collections import defaultdict, deque
from datetime import date
from importlib import resources
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from bejitech import APP_NAME, __version__
from bejitech.config.paths import AppPaths
from bejitech.core.errors import BejitechError, KeyStoreError
from bejitech.core.money import format_money
from bejitech.core.timeutil import display_date, display_datetime
from bejitech.db.engine import Database
from bejitech.db.migrations import migrate
from bejitech.security.keystore import EnvKeyStore, KeyStore
from bejitech.services.common import get_setting
from bejitech.services.context import AppContext
from bejitech.web.config import WebConfig

log = logging.getLogger("bejitech.web")

PACKAGE_DIR = Path(str(resources.files("bejitech.web")))
STAGE_FULL, STAGE_TWO_STEP, STAGE_ENROL = "full", "two_step", "enrol"

PERIODS = {"all": "All time", "month": "This month", "30d": "Last 30 days", "year": "This year"}


def period_range(key: str) -> tuple[str | None, str | None]:
    t = date.today()
    if key == "month":
        return t.replace(day=1).isoformat(), t.isoformat()
    if key == "30d":
        return date.fromordinal(t.toordinal() - 29).isoformat(), t.isoformat()
    if key == "year":
        return t.replace(month=1, day=1).isoformat(), t.isoformat()
    return None, None


class LoginRequired(Exception):
    def __init__(self, to: str = "/login"):
        self.to = to


class WebState:
    """Things shared by all requests: database, key store and the licence-key cipher."""

    def __init__(self, config: WebConfig, keystore: KeyStore | None = None):
        self.config = config
        self.paths = AppPaths(root=config.data_dir, logs=config.data_dir / "logs",
                              database_url=config.database_url).ensure()
        migrate(self.paths.database_target, self.paths.backups)
        self.db = Database(self.paths.database_target)
        self.keystore = keystore or EnvKeyStore()
        self._cipher = None

    def ctx(self, user_id: int | None = None) -> AppContext:
        return AppContext(paths=self.paths, db=self.db, keystore=self.keystore,
                          cipher=self.cipher(), user_id=user_id)

    def cipher(self):
        if self._cipher is None:
            probe = AppContext(paths=self.paths, db=self.db, keystore=self.keystore)
            try:
                self._cipher = probe.auth.cipher_from_keystore()
            except KeyStoreError:
                log.error("Licence-key encryption key missing or wrong (BEJITECH_DEK)")
                return None
        return self._cipher

    def autolock_seconds(self) -> int:
        with self.db.session() as s:
            minutes = get_setting(s, "security.autolock_minutes", "15")
        try:
            return max(5, int(minutes)) * 60
        except ValueError:
            return 15 * 60


class RateLimiter:
    """At most `limit` attempts per `window` seconds for each client address."""

    def __init__(self, limit: int = 20, window: int = 600):
        self.limit, self.window = limit, window
        self.hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        q = self.hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        return True


def create_app(config: WebConfig | None = None, keystore: KeyStore | None = None) -> FastAPI:
    config = config or WebConfig.from_env()
    state = WebState(config, keystore)
    limiter = RateLimiter()

    app = FastAPI(title=APP_NAME, version=__version__, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.web = state
    templates = Jinja2Templates(directory=str(PACKAGE_DIR / "templates"))
    templates.env.globals.update(app_name=APP_NAME, version=__version__, format_money=format_money,
                                 display_date=display_date, display_datetime=display_datetime)

    # ---------- middleware ----------
    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
            "frame-ancestors 'none'; form-action 'self'; base-uri 'none'")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = response.headers.get("Cache-Control", "no-store")
        if config.cookie_secure:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    app.add_middleware(SessionMiddleware, secret_key=config.secret_key, session_cookie="bejitech_session",
                       max_age=config.session_max_hours * 3600, same_site="lax", https_only=config.cookie_secure)

    app.mount("/static", StaticFiles(directory=str(PACKAGE_DIR / "static")), name="static")

    @app.exception_handler(LoginRequired)
    async def _login_required(request: Request, exc: LoginRequired):
        return RedirectResponse(exc.to, status_code=303)

    # ---------- helpers ----------
    def csrf_token(request: Request) -> str:
        tok = request.session.get("csrf")
        if not tok:
            tok = secrets.token_urlsafe(32)
            request.session["csrf"] = tok
        return tok

    def check_csrf(request: Request, token: str) -> None:
        expected = request.session.get("csrf", "")
        if not expected or not hmac.compare_digest(expected, token or ""):
            raise LoginRequired("/login?expired=1")

    def render(request: Request, name: str, status: int = 200, **ctx) -> HTMLResponse:
        ctx.setdefault("user", request.session.get("name"))
        return templates.TemplateResponse(request, name, {"csrf": csrf_token(request), "path": request.url.path,
                                                          **ctx}, status_code=status)

    def from_this_computer(request: Request) -> bool:
        """Local runs only: the browser is on the computer running the app."""
        host = request.client.host if request.client else ""
        return config.local_mode and host in ("127.0.0.1", "::1", "localhost")

    def setup_code_ok(request: Request, typed: str) -> bool:
        if from_this_computer(request):
            return True
        typed = typed.strip().strip('"').strip("'")
        if typed.upper().startswith("BEJITECH_SETUP_TOKEN="):
            typed = typed.split("=", 1)[1].strip()
        return bool(config.setup_token) and hmac.compare_digest(config.setup_token, typed)

    def client_key(request: Request) -> str:
        return request.client.host if request.client else "unknown"

    def start_stage(request: Request, uid: int, name: str, stage: str) -> None:
        csrf = request.session.get("csrf")
        request.session.clear()  # new session on every sign-in step (no fixation)
        now = int(time.time())
        request.session.update(uid=uid, name=name, stage=stage, t_stage=now, t_seen=now, t_auth=now,
                               csrf=csrf or secrets.token_urlsafe(32))

    def require_user(request: Request) -> int:
        """Return the signed-in user id or send the browser to the right sign-in step."""
        s = request.session
        uid = s.get("uid")
        if not uid:
            raise LoginRequired("/setup" if not state.ctx().auth.has_users() else "/login")
        now = int(time.time())
        if s.get("stage") == STAGE_TWO_STEP:
            raise LoginRequired("/login/code")
        if s.get("stage") == STAGE_ENROL:
            raise LoginRequired("/setup/two-step")
        if s.get("stage") != STAGE_FULL or now - int(s.get("t_seen", 0)) > state.autolock_seconds():
            s.clear()
            raise LoginRequired("/login?idle=1")
        s["t_seen"] = now
        return int(uid)

    def require_cipher_ready() -> None:
        if state.cipher() is None and state.ctx().auth.has_users():
            raise BejitechError("The server's encryption key (BEJITECH_DEK) is missing or wrong.")

    # ---------- health ----------
    @app.get("/healthz", response_class=PlainTextResponse)
    def healthz():
        with state.db.session() as s:
            get_setting(s, "seller.name")
        return "ok"

    # ---------- first-run setup ----------
    @app.get("/setup", response_class=HTMLResponse)
    def setup_form(request: Request):
        if state.ctx().auth.has_users():
            return RedirectResponse("/login", status_code=303)
        return render(request, "setup.html", error=None, form={}, need_code=not from_this_computer(request))

    @app.post("/setup", response_class=HTMLResponse)
    def setup_submit(request: Request, csrf: str = Form(""), setup_token: str = Form(""),
                     display_name: str = Form(""), username: str = Form(""), password: str = Form(""),
                     password2: str = Form(""), recovery: str = Form("")):
        check_csrf(request, csrf)
        ctx = state.ctx()
        if ctx.auth.has_users():
            return RedirectResponse("/login", status_code=303)
        form = {"display_name": display_name, "username": username}
        error = None
        if not limiter.allow("setup:" + client_key(request)):
            error = "Too many attempts. Please wait a few minutes."
        elif not setup_code_ok(request, setup_token):
            error = ("The setup code is not correct. Copy it exactly from the Terminal window (the line "
                     "'Setup code'), or open this page on the computer running the app."
                     if config.local_mode else
                     "The setup code is not correct. It is the BEJITECH_SETUP_TOKEN value on the server.")
        elif password != password2:
            error = "The two passwords do not match."
        elif state.keystore.load() is None:
            error = "The server's encryption key (BEJITECH_DEK) is not set yet."
        if error:
            return render(request, "setup.html", status=400, error=error, form=form,
                          need_code=not from_this_computer(request))
        try:
            ctx.auth.create_admin(display_name, username, password, recovery)
        except BejitechError as exc:
            return render(request, "setup.html", status=400, error=str(exc), form=form,
                          need_code=not from_this_computer(request))
        state._cipher = None
        start_stage(request, ctx.user_id, ctx.auth.display_name, STAGE_ENROL)
        return RedirectResponse("/setup/two-step", status_code=303)

    @app.get("/setup/two-step", response_class=HTMLResponse)
    def enrol_form(request: Request):
        if request.session.get("stage") != STAGE_ENROL:
            raise LoginRequired("/login")
        secret = request.session.get("totp_secret")
        if not secret:
            secret = state.ctx().auth.new_totp_secret()
            request.session["totp_secret"] = secret
        return render(request, "enrol.html", **_enrol_view(state, request, secret), error=None)

    @app.post("/setup/two-step", response_class=HTMLResponse)
    def enrol_submit(request: Request, csrf: str = Form(""), code: str = Form("")):
        check_csrf(request, csrf)
        s = request.session
        if s.get("stage") != STAGE_ENROL or not s.get("totp_secret"):
            raise LoginRequired("/login")
        ctx = state.ctx(int(s["uid"]))
        try:
            ctx.auth.enable_totp(int(s["uid"]), s["totp_secret"], code)
        except BejitechError as exc:
            return render(request, "enrol.html", status=400, **_enrol_view(state, request, s["totp_secret"]),
                          error=str(exc))
        start_stage(request, int(s["uid"]), s.get("name", ""), STAGE_FULL)
        return RedirectResponse("/", status_code=303)

    # ---------- sign in ----------
    @app.get("/login", response_class=HTMLResponse)
    def login_form(request: Request, idle: int = 0, expired: int = 0):
        if not state.ctx().auth.has_users():
            return RedirectResponse("/setup", status_code=303)
        note = ("You were signed out after a period of inactivity." if idle else
                "Your session expired. Please sign in again." if expired else None)
        return render(request, "login.html", error=None, note=note, username="")

    @app.post("/login", response_class=HTMLResponse)
    def login_submit(request: Request, csrf: str = Form(""), username: str = Form(""), password: str = Form("")):
        check_csrf(request, csrf)
        if not limiter.allow("login:" + client_key(request)):
            return render(request, "login.html", status=429, note=None, username=username,
                          error="Too many attempts from this device. Please wait 10 minutes.")
        ctx = state.ctx()
        try:
            require_cipher_ready()
            uid, _uname, dname = ctx.auth.verify_credentials(username, password)
        except BejitechError as exc:
            return render(request, "login.html", status=400, error=str(exc), note=None, username=username)
        stage = STAGE_TWO_STEP if ctx.auth.totp_enabled(uid) else STAGE_ENROL
        start_stage(request, uid, dname, stage)
        return RedirectResponse("/login/code" if stage == STAGE_TWO_STEP else "/setup/two-step", status_code=303)

    @app.get("/login/code", response_class=HTMLResponse)
    def code_form(request: Request):
        if request.session.get("stage") != STAGE_TWO_STEP:
            raise LoginRequired("/login")
        return render(request, "code.html", error=None)

    @app.post("/login/code", response_class=HTMLResponse)
    def code_submit(request: Request, csrf: str = Form(""), code: str = Form("")):
        check_csrf(request, csrf)
        s = request.session
        if s.get("stage") != STAGE_TWO_STEP:
            raise LoginRequired("/login")
        if int(time.time()) - int(s.get("t_stage", 0)) > config.two_step_pending_seconds:
            s.clear()
            raise LoginRequired("/login?expired=1")
        if not limiter.allow("code:" + client_key(request)):
            return render(request, "code.html", status=429, error="Too many attempts. Please wait 10 minutes.")
        try:
            state.ctx(int(s["uid"])).auth.verify_totp(int(s["uid"]), code)
        except BejitechError as exc:
            return render(request, "code.html", status=400, error=str(exc))
        start_stage(request, int(s["uid"]), s.get("name", ""), STAGE_FULL)
        return RedirectResponse("/", status_code=303)

    @app.post("/logout")
    def logout(request: Request, csrf: str = Form("")):
        check_csrf(request, csrf)
        request.session.clear()
        return RedirectResponse("/login", status_code=303)

    # ---------- pages ----------
    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request, period: str = "all"):
        uid = require_user(request)
        ctx = state.ctx(uid)
        period = period if period in PERIODS else "all"
        d = ctx.reports.dashboard(*period_range(period))
        sales = ctx.sales.list_sales()[:10]
        return render(request, "dashboard.html", d=d, sales=sales, periods=PERIODS, period=period,
                      today=date.today().isoformat())

    @app.get("/products", response_class=HTMLResponse)
    def products(request: Request, q: str = "", archived: int = 0):
        uid = require_user(request)
        rows = state.ctx(uid).catalogue.list_products(search=q.strip(), include_archived=bool(archived))
        return render(request, "products.html", products=rows, q=q, archived=archived)

    @app.get("/logo/{product_id}")
    def logo(request: Request, product_id: int):
        uid = require_user(request)
        ctx = state.ctx(uid)
        try:
            p = ctx.catalogue.get_product(product_id)
        except BejitechError:
            return Response(status_code=404)
        f = ctx.catalogue.logo_file(p.logo_path)
        if not f:
            return Response(status_code=404)
        return FileResponse(f, headers={"Cache-Control": "private, max-age=3600"})

    return app


def _enrol_view(state: WebState, request: Request, secret: str) -> dict:
    import qrcode
    import qrcode.image.svg

    uri = state.ctx().auth.totp_provisioning_uri(secret, request.session.get("name") or "admin")
    svg = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=2).to_string(
        encoding="unicode")
    grouped = " ".join(secret[i:i + 4] for i in range(0, len(secret), 4))
    return {"qr_svg": svg, "secret": grouped}
