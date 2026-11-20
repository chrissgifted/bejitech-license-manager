"""Web version: first-run setup, two-step login, sessions and the first pages.

Runs on SQLite by default and on PostgreSQL when BEJITECH_TEST_DATABASE_URL is set."""
import re
import time

import pyotp
import pytest
from fastapi.testclient import TestClient

from conftest import PASSWORD, PG_URL, RECOVERY, _reset_pg_schema
from bejitech.security import crypto
from bejitech.security.keystore import MemoryKeyStore
from bejitech.web import main as web_main
from bejitech.web.config import WebConfig

SETUP = "setup-code-123"


@pytest.fixture
def client(tmp_path):
    if PG_URL:
        _reset_pg_schema(PG_URL)
    config = WebConfig(data_dir=tmp_path / "web", database_url=PG_URL, secret_key="x" * 40,
                       setup_token=SETUP, cookie_secure=False)
    app = web_main.create_app(config, keystore=MemoryKeyStore(crypto.generate_key()))
    with TestClient(app, follow_redirects=False) as c:
        yield c
    app.state.web.db.dispose()


def csrf(html: str) -> str:
    return re.search(r'name="csrf" value="([^"]+)"', html).group(1)


def setup_admin(client) -> str:
    """Create the administrator and turn on two-step login. Returns the authenticator secret."""
    page = client.get("/setup")
    r = client.post("/setup", data={"csrf": csrf(page.text), "setup_token": SETUP, "display_name": "Christian Joel Mtei",
                                    "username": "admin", "password": PASSWORD, "password2": PASSWORD,
                                    "recovery": RECOVERY})
    assert r.status_code == 303 and r.headers["location"] == "/setup/two-step"
    page = client.get("/setup/two-step")
    assert "<svg" in page.text
    secret = re.search(r'<code class="secret">([A-Z2-7 ]+)</code>', page.text).group(1).replace(" ", "")
    r = client.post("/setup/two-step", data={"csrf": csrf(page.text), "code": pyotp.TOTP(secret).now()})
    assert r.status_code == 303 and r.headers["location"] == "/"
    return secret


def sign_out(client):
    page = client.get("/")
    client.post("/logout", data={"csrf": csrf(page.text)})


def test_fresh_server_goes_to_setup(client):
    assert client.get("/").headers["location"] == "/setup"
    assert client.get("/login").headers["location"] == "/setup"
    assert client.get("/healthz").text == "ok"


def test_setup_needs_the_setup_code(client):
    page = client.get("/setup")
    r = client.post("/setup", data={"csrf": csrf(page.text), "setup_token": "wrong", "display_name": "X",
                                    "username": "x", "password": PASSWORD, "password2": PASSWORD,
                                    "recovery": RECOVERY})
    assert r.status_code == 400 and "setup code is not correct" in r.text
    assert client.get("/").headers["location"] == "/setup"


def test_setup_then_dashboard_and_products(client):
    setup_admin(client)
    r = client.get("/")
    assert r.status_code == 200 and "Dashboard" in r.text and "Christian Joel Mtei" in r.text
    r = client.get("/?period=month")
    assert r.status_code == 200
    r = client.get("/products")
    assert r.status_code == 200
    for name in ("Microsoft Office 2019 Professional Plus", "Windows 11 Pro"):
        assert name in r.text
    r = client.get("/products?q=windows")
    assert "Windows 11 Pro" in r.text and "Office 2019" not in r.text
    assert client.get("/setup").headers["location"] == "/login"  # setup can't run twice


def test_two_step_login(client):
    secret = setup_admin(client)
    sign_out(client)
    assert client.get("/").headers["location"] == "/login"
    page = client.get("/login")
    r = client.post("/login", data={"csrf": csrf(page.text), "username": "ADMIN", "password": PASSWORD})
    assert r.headers["location"] == "/login/code"
    assert client.get("/").headers["location"] == "/login/code"  # password alone is not enough
    page = client.get("/login/code")
    r = client.post("/login/code", data={"csrf": csrf(page.text), "code": "000000"})
    assert r.status_code == 400
    nxt = pyotp.TOTP(secret).at(time.time() + 30)  # the code used at setup can't be replayed
    r = client.post("/login/code", data={"csrf": csrf(page.text), "code": nxt})
    assert r.status_code == 303 and r.headers["location"] == "/"
    assert client.get("/").status_code == 200


def test_wrong_password_and_lockout(client):
    setup_admin(client)
    sign_out(client)
    page = client.get("/login")
    token = csrf(page.text)
    for _ in range(5):
        r = client.post("/login", data={"csrf": token, "username": "admin", "password": "wrong-password"})
        assert r.status_code == 400 and "Incorrect" in r.text
    r = client.post("/login", data={"csrf": token, "username": "admin", "password": PASSWORD})
    assert r.status_code == 400 and "wait" in r.text


def test_forms_need_csrf_token(client):
    setup_admin(client)
    r = client.post("/logout", data={"csrf": "forged"})
    assert r.headers["location"].startswith("/login")
    assert client.get("/").status_code == 200  # the forged request did nothing


def test_idle_sign_out(client, monkeypatch):
    setup_admin(client)
    assert client.get("/").status_code == 200
    later = time.time() + 16 * 60
    monkeypatch.setattr(web_main.time, "time", lambda: later)
    r = client.get("/")
    assert r.headers["location"] == "/login?idle=1"


def test_pages_need_sign_in_and_send_security_headers(client):
    setup_admin(client)
    sign_out(client)
    for url in ("/", "/products", "/logo/1"):
        assert client.get(url).headers["location"] == "/login"
    r = client.get("/login")
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert r.headers["x-frame-options"] == "DENY"
    assert "httponly" in r.headers["set-cookie"].lower()


def test_licence_key_cipher_comes_from_server_key(client):
    setup_admin(client)
    state = client.app.state.web
    assert state.cipher() is not None
    ctx = state.ctx(1)
    assert ctx.auth.totp_enabled(1)


def test_reset_two_step_command(client, monkeypatch, tmp_path):
    from bejitech.web import __main__ as cli
    setup_admin(client)
    state = client.app.state.web
    monkeypatch.setattr("bejitech.web.main.WebState", lambda config: state)
    monkeypatch.setenv("BEJITECH_SECRET_KEY", "y" * 40)
    assert cli.main(["x", "reset-two-step", "Admin"]) == 0
    assert not state.ctx(1).auth.totp_enabled(1)
    assert cli.main(["x", "reset-two-step", "nobody"]) == 1


def test_setup_code_tolerates_pasted_prefix(client):
    page = client.get("/setup")
    r = client.post("/setup", data={"csrf": csrf(page.text), "setup_token": f"  BEJITECH_SETUP_TOKEN={SETUP} ",
                                    "display_name": "X", "username": "x", "password": PASSWORD,
                                    "password2": PASSWORD, "recovery": RECOVERY})
    assert r.status_code == 303


def test_local_mode_needs_no_setup_code_on_the_same_computer(tmp_path):
    if PG_URL:
        _reset_pg_schema(PG_URL)
    config = WebConfig(data_dir=tmp_path / "web", database_url=PG_URL, secret_key="x" * 40,
                       setup_token=SETUP, cookie_secure=False, local_mode=True)
    app = web_main.create_app(config, keystore=MemoryKeyStore(crypto.generate_key()))
    with TestClient(app, follow_redirects=False, client=("192.168.1.50", 5000)) as other:
        page = other.get("/setup")
        assert 'name="setup_token"' in page.text  # another device on the Wi-Fi still needs the code
    with TestClient(app, follow_redirects=False, client=("127.0.0.1", 5000)) as here:
        page = here.get("/setup")
        assert 'name="setup_token"' not in page.text
        r = here.post("/setup", data={"csrf": csrf(page.text), "display_name": "X", "username": "x",
                                      "password": PASSWORD, "password2": PASSWORD, "recovery": RECOVERY})
        assert r.status_code == 303 and r.headers["location"] == "/setup/two-step"
    app.state.web.db.dispose()


def test_password_only_sign_in_when_two_step_is_off(tmp_path, monkeypatch):
    """Local laptop default: no 6-digit code at setup or sign-in."""
    monkeypatch.setenv("BEJITECH_SECRET_KEY", "x" * 40)
    monkeypatch.setenv("BEJITECH_LOCAL_MODE", "1")
    monkeypatch.delenv("BEJITECH_TWO_STEP", raising=False)
    assert WebConfig.from_env().two_step is False
    monkeypatch.setenv("BEJITECH_LOCAL_MODE", "0")
    assert WebConfig.from_env().two_step is True  # online: always on unless explicitly turned off

    if PG_URL:
        _reset_pg_schema(PG_URL)
    config = WebConfig(data_dir=tmp_path / "web", database_url=PG_URL, secret_key="x" * 40,
                       setup_token=SETUP, cookie_secure=False, two_step=False)
    app = web_main.create_app(config, keystore=MemoryKeyStore(crypto.generate_key()))
    with TestClient(app, follow_redirects=False) as c:
        page = c.get("/setup")
        r = c.post("/setup", data={"csrf": csrf(page.text), "setup_token": SETUP, "display_name": "X",
                                   "username": "admin", "password": PASSWORD, "password2": PASSWORD,
                                   "recovery": RECOVERY})
        assert r.status_code == 303 and r.headers["location"] == "/"
        assert c.get("/").status_code == 200
        sign_out(c)
        page = c.get("/login")
        r = c.post("/login", data={"csrf": csrf(page.text), "username": "admin", "password": PASSWORD})
        assert r.status_code == 303 and r.headers["location"] == "/"
        assert "password only" in c.get("/settings?tab=security").text
        assert c.get("/login/code").status_code == 303
    app.state.web.db.dispose()
