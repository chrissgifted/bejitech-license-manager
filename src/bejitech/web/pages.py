"""All business screens of the web version, in the same order as the desktop app's sidebar.

Every action goes through the existing services, so the rules (stock, allocation, cancellation,
audit log, delivery notes) are exactly the desktop app's. Forms post back with a CSRF token;
user-facing errors from the services are shown on the same form.
"""
from __future__ import annotations

import re
import tempfile
import time
from datetime import date
from pathlib import Path
from urllib.parse import quote, urlencode

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response

from bejitech.core.dto import CustomerInput, LicenseInput, ProductInput, SaleInput
from bejitech.core.enums import PaymentMethod, StockState
from bejitech.core.errors import BejitechError, ValidationError
from bejitech.core.money import convert_to_tzs, format_money, from_minor, to_minor
from bejitech.core.timeutil import display_date, display_datetime, today_iso
from bejitech.security.keystore import EnvFileKeyStore, EnvKeyStore

PLATFORMS = ["Windows", "macOS", "Windows & macOS", "Linux", "Cross-platform", "Android", "iOS"]
REPORTS = [("inventory", "Inventory"), ("sales", "Sales"), ("customers", "Customers"),
           ("activations", "Activation balances"), ("profit", "Profit")]
PERIODS = {"all": "All time", "month": "This month", "30d": "Last 30 days", "year": "This year"}
STATES = [("", "All")] + [(s.value, s.label) for s in StockState]
SETTINGS_TABS = [("business", "Business"), ("sales", "Sales & currency"), ("types", "Licence types"),
                 ("delivery", "Delivery notes"), ("security", "Security"), ("audit", "Audit log"),
                 ("about", "About")]
REAUTH_SECONDS = 5 * 60
# Report columns that hold TZS amounts (shown with the currency on screen)
MONEY_COLS = {"Cost TZS", "Subtotal", "Discount", "Total", "Total spent TZS", "Revenue", "Cost of keys sold",
              "Cancelled & consumed", "Gross profit"}


def period_range(key: str) -> tuple[str | None, str | None]:
    t = date.today()
    if key == "month":
        return t.replace(day=1).isoformat(), t.isoformat()
    if key == "30d":
        return date.fromordinal(t.toordinal() - 29).isoformat(), t.isoformat()
    if key == "year":
        return t.replace(month=1, day=1).isoformat(), t.isoformat()
    return None, None


def _money_input(minor: int | None, currency: str = "TZS") -> str:
    if not minor:
        return ""
    v = from_minor(minor, currency)
    return f"{v:,.0f}" if currency == "TZS" else f"{v:,.2f}"


def _int(value, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _opt_int(value) -> int | None:
    v = _int(value, 0)
    return v or None


def register(app: FastAPI, ui) -> None:  # noqa: C901 - one place for all screens
    state = ui.state
    templates_globals = {
        "format_money": format_money, "display_date": display_date, "display_datetime": display_datetime,
        "payment_label": lambda v: PaymentMethod(v).label if v in PaymentMethod.__members__ else v,
        "state_label": lambda v: StockState(v).label if v in StockState.__members__ else v,
        "money_input": _money_input, "quote": quote,
        "expiry_label": lambda v: display_date(v) if v else "Lifetime",
        "abs": abs,
    }

    def page(request: Request, name: str, status: int = 200, **kw) -> HTMLResponse:
        return ui.render(request, name, status=status, **templates_globals, **kw)

    def go(url: str) -> RedirectResponse:
        return RedirectResponse(url, status_code=303)

    def flash(request: Request, message: str, kind: str = "ok") -> None:
        request.session["flash"] = request.session.get("flash", []) + [[kind, message]]

    def ctx_of(request: Request):
        return state.ctx(ui.require_user(request))

    async def posted(request: Request) -> dict:
        form = await request.form()
        ui.check_csrf(request, str(form.get("csrf", "")))
        return form

    def recently_authenticated(request: Request) -> bool:
        return int(time.time()) - int(request.session.get("t_auth", 0)) <= REAUTH_SECONDS

    # ======================= Dashboard =======================
    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request, period: str = "all"):
        ctx = ctx_of(request)
        period = period if period in PERIODS else "all"
        d = ctx.reports.dashboard(*period_range(period))
        balances = ctx.accounts.balances()
        owing = sorted(((b, cid) for cid, b in balances.items() if b > 0), reverse=True)[:8]
        names = {c.id: c.full_name for c in ctx.customers.list(include_archived=True)}
        return page(request, "dashboard.html", d=d, sales=ctx.sales.list_sales()[:12], periods=PERIODS,
                    period=period, today=today_iso(), owed=sum(b for b in balances.values() if b > 0),
                    debtors=[(names.get(cid, "?"), cid, b) for b, cid in owing],
                    pay=ctx.accounts.sale_states())

    # ======================= Software products =======================
    @app.get("/products", response_class=HTMLResponse)
    def products(request: Request, q: str = "", archived: int = 0):
        ctx = ctx_of(request)
        rows = ctx.catalogue.list_products(search=q.strip(), include_archived=bool(archived))
        return page(request, "products.html", products=rows, q=q, archived=archived)

    def product_form_view(request, ctx, product=None, form=None, error=None, status=200):
        return page(request, "product_form.html", status=status, product=product, form=form or {}, error=error,
                    publishers=ctx.catalogue.list_publishers(), categories=ctx.catalogue.list_categories(),
                    lines=ctx.catalogue.list_product_lines(), types=ctx.catalogue.list_license_types(),
                    platforms=PLATFORMS)

    def product_to_form(p) -> dict:
        return {"id": p.id, "publisher": p.publisher, "category": p.category, "line": p.product_line,
                "version": p.version, "edition": p.edition, "platform": p.platform,
                "license_type_id": p.license_type_id, "display_name": p.display_name, "sku": p.sku_code or "",
                "low": p.low_stock_threshold, "cost": _money_input(p.purchase_price_minor, p.purchase_currency),
                "cost_currency": p.purchase_currency, "price": _money_input(p.selling_price_minor),
                "url": p.download_url or "", "label": p.download_label or "",
                "verified": p.download_url_verified, "install": p.installation_instructions or "",
                "activate": p.activation_instructions or ""}

    @app.get("/products/new", response_class=HTMLResponse)
    def product_new(request: Request):
        ctx = ctx_of(request)
        low = ctx.settings.get_int("inventory.default_low_stock", 3)
        return product_form_view(request, ctx, form={"publisher": "Microsoft", "platform": "Windows", "low": low,
                                                     "cost_currency": "TZS"})

    @app.get("/products/{pid}/edit", response_class=HTMLResponse)
    def product_edit(request: Request, pid: int):
        ctx = ctx_of(request)
        p = ctx.catalogue.get_product(pid)
        return product_form_view(request, ctx, product=p, form=product_to_form(p))

    @app.post("/products/save", response_class=HTMLResponse)
    async def product_save(request: Request):
        ctx = ctx_of(request)
        f = await posted(request)
        pid = _opt_int(f.get("id"))
        product = ctx.catalogue.get_product(pid) if pid else None
        try:
            cur = str(f.get("cost_currency") or "TZS")
            data = ProductInput(
                id=pid, publisher_name=str(f.get("publisher", "")), category_name=str(f.get("category", "")),
                product_line_name=str(f.get("line", "")), version=str(f.get("version", "")),
                edition=str(f.get("edition", "")), platform=str(f.get("platform") or "Windows"),
                license_type_id=_int(f.get("license_type_id")), display_name=str(f.get("display_name", "")),
                sku_code=str(f.get("sku", "")), purchase_price_minor=to_minor(f.get("cost", ""), cur),
                purchase_currency=cur, selling_price_minor=to_minor(f.get("price", ""), "TZS"),
                download_url=str(f.get("url", "")), download_label=str(f.get("label", "")),
                download_url_verified=bool(f.get("verified")),
                installation_instructions=str(f.get("install", "")),
                activation_instructions=str(f.get("activate", "")), low_stock_threshold=_int(f.get("low"), 3))
            new_id = ctx.catalogue.save_product(data)
            logo = f.get("logo")
            if logo is not None and getattr(logo, "filename", ""):
                content = await logo.read()
                suffix = Path(logo.filename).suffix.lower() or ".png"
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                    tmp.write(content)
                try:
                    ctx.catalogue.set_logo(new_id, tmp.name)
                finally:
                    Path(tmp.name).unlink(missing_ok=True)
            elif f.get("remove_logo"):
                ctx.catalogue.set_logo(new_id, None)
        except BejitechError as exc:
            return product_form_view(request, ctx, product=product, form=dict(f), error=str(exc), status=400)
        flash(request, f"Saved {ctx.catalogue.get_product(new_id).display_name}.")
        return go("/products")

    @app.post("/products/{pid}/archive")
    async def product_archive(request: Request, pid: int):
        ctx = ctx_of(request)
        f = await posted(request)
        archive = f.get("archived") == "1"
        try:
            ctx.catalogue.set_archived(pid, archive)
            flash(request, "Product archived." if archive else "Product restored.")
        except BejitechError as exc:
            flash(request, str(exc), "error")
        return go("/products" + ("?archived=1" if not archive else ""))

    @app.get("/logo/{product_id}")
    def logo(request: Request, product_id: int):
        ctx = ctx_of(request)
        try:
            p = ctx.catalogue.get_product(product_id)
        except BejitechError:
            return Response(status_code=404)
        f = ctx.catalogue.logo_file(p.logo_path)
        if not f:
            return Response(status_code=404)
        return FileResponse(f, headers={"Cache-Control": "private, max-age=300"})

    # ======================= Licence inventory =======================
    @app.get("/inventory", response_class=HTMLResponse)
    def inventory(request: Request, q: str = "", product: int = 0, id: int = 0):
        ctx = ctx_of(request)
        st = request.query_params.get("state", "")
        rows = ctx.inventory.list_licenses(search=q.strip(), state=st or None, product_id=product or None)
        sel = hist = None
        if id:
            try:
                sel = ctx.inventory.get_license(id)
                hist = list(reversed(ctx.inventory.history(id)))
            except BejitechError:
                sel = None
        revealed = request.session.pop("revealed", None)
        if not (revealed and sel and revealed.get("id") == sel.id):
            revealed = None
        return page(request, "inventory.html", rows=rows, q=q, state=st, product=product, sel=sel, hist=hist,
                    states=STATES, products=ctx.catalogue.list_products(include_archived=True),
                    revealed=revealed, need_password=not recently_authenticated(request),
                    base=urlencode({k: v for k, v in (("q", q), ("product", product or "")) if v}),
                    query=urlencode({k: v for k, v in (("q", q), ("state", st), ("product", product or ""))
                                     if v}))

    def license_form_view(request, ctx, lic=None, form=None, error=None, status=200):
        products = ctx.catalogue.list_products()
        types = ctx.catalogue.list_license_types()
        return page(request, "license_form.html", status=status, lic=lic, form=form or {}, error=error,
                    products=products, types=types, suppliers=ctx.inventory.list_suppliers(),
                    changeable=ctx.inventory.can_change_product(lic.id) if lic else True,
                    product_types={p.id: p.license_type_id for p in products},
                    type_defaults={t["id"]: t for t in types})

    @app.get("/inventory/new", response_class=HTMLResponse)
    def license_new(request: Request, product: int = 0):
        ctx = ctx_of(request)
        return license_form_view(request, ctx, form={
            "product_id": product, "purchase_date": today_iso(), "currency": "TZS",
            "rate": ctx.settings.get("currency.usd_rate", "2650"), "capacity": 1})

    @app.get("/inventory/{lid}/edit", response_class=HTMLResponse)
    def license_edit(request: Request, lid: int):
        ctx = ctx_of(request)
        lic = ctx.inventory.get_license(lid)
        prod = ctx.catalogue.get_product(lic.product_id)
        return license_form_view(request, ctx, lic=lic, form={
            "product_id": lic.product_id, "license_type_id": prod.license_type_id, "supplier": lic.supplier or "",
            "multi": lic.allows_multiple_customers, "reassign": lic.reassignable,
            "expiry": lic.expiration_date or "", "restrictions": lic.restrictions or "", "notes": lic.notes or ""})

    @app.post("/inventory/save", response_class=HTMLResponse)
    async def license_save(request: Request):
        ctx = ctx_of(request)
        f = await posted(request)
        lid = _opt_int(f.get("id"))
        lic = ctx.inventory.get_license(lid) if lid else None
        form = dict(f)
        form["multi"], form["reassign"] = bool(f.get("multi")), bool(f.get("reassign"))
        if f.get("validity") == "lifetime":
            form["expiry"] = ""  # lifetime activation: no expiry date
        try:
            product_id = _int(f.get("product_id"))
            type_id = _opt_int(f.get("license_type_id"))
            if lic:
                ctx.inventory.update_license(
                    lid, supplier_name=str(f.get("supplier", "")), restrictions=str(f.get("restrictions", "")),
                    expiration_date=str(form.get("expiry", "")), notes=str(f.get("notes", "")),
                    allows_multiple_customers=form["multi"], reassignable=form["reassign"],
                    product_id=product_id or None, license_type_id=type_id)
                flash(request, f"Saved {lic.inventory_ref}.")
                return go(f"/inventory?id={lid}")
            if not product_id:
                raise ValidationError("Please choose a product (add one under Software Products first).")
            cur = str(f.get("currency") or "TZS")
            tmpl = LicenseInput(
                product_id=product_id, license_key="", purchase_date=str(f.get("purchase_date", "")),
                purchase_cost_minor=to_minor(f.get("cost", ""), cur), permitted_capacity=_int(f.get("capacity"), 0),
                purchase_currency=cur, exchange_rate_to_tzs=str(f.get("rate", "1")) if cur == "USD" else "1",
                supplier_name=str(f.get("supplier", "")), allows_multiple_customers=form["multi"],
                reassignable=form["reassign"], restrictions=str(f.get("restrictions", "")),
                expiration_date=str(form.get("expiry", "")), notes=str(f.get("notes", "")))
            prod = ctx.catalogue.get_product(product_id)
            if type_id and type_id != prod.license_type_id:
                tmpl.product_id = ctx.catalogue.variant_for_type(product_id, type_id)
            keys = [k for k in str(f.get("keys", "")).splitlines() if k.strip()]
            if not keys:
                raise ValidationError("Please enter the licence key.")
            if len(keys) == 1:
                tmpl.license_key = keys[0]
                new_id = ctx.inventory.add_license(tmpl)
                flash(request, "Licence key added.")
                return go(f"/inventory?id={new_id}")
            ids = ctx.inventory.add_licenses_bulk(keys, tmpl)
            flash(request, f"{len(ids)} licence keys added.")
            return go("/inventory")
        except BejitechError as exc:
            return license_form_view(request, ctx, lic=lic, form=form, error=str(exc), status=400)

    @app.post("/inventory/{lid}/reveal")
    async def license_reveal(request: Request, lid: int):
        ctx = ctx_of(request)
        f = await posted(request)
        try:
            if not recently_authenticated(request):
                ctx.auth.check_password(ctx.user_id, str(f.get("password", "")))
                request.session["t_auth"] = int(time.time())
            key = ctx.inventory.reveal_key(lid, "reveal")
            request.session["revealed"] = {"id": lid, "key": key}
        except BejitechError as exc:
            flash(request, str(exc), "error")
        return go(f"/inventory?id={lid}")

    @app.post("/inventory/{lid}/copied")
    async def license_copied(request: Request, lid: int):
        ctx = ctx_of(request)
        await posted(request)
        with ctx.db.session() as s:  # audit only; the key was already revealed to this user
            from bejitech.db.models import License
            from bejitech.services.common import audit
            lic = s.get(License, lid)
            if lic:
                audit(s, ctx.user_id, "KEY_COPIED", "license", lic.uuid, ref=lic.inventory_ref)
        return JSONResponse({"ok": True})

    @app.post("/inventory/{lid}/capacity")
    async def license_capacity(request: Request, lid: int):
        ctx = ctx_of(request)
        f = await posted(request)
        try:
            ctx.inventory.adjust_capacity(lid, _int(f.get("capacity")), str(f.get("reason", "")))
            flash(request, "Capacity updated.")
        except BejitechError as exc:
            flash(request, str(exc), "error")
        return go(f"/inventory?id={lid}")

    @app.post("/inventory/{lid}/disable")
    async def license_disable(request: Request, lid: int):
        ctx = ctx_of(request)
        f = await posted(request)
        disable = f.get("disable") == "1"
        try:
            ctx.inventory.set_disabled(lid, disable, str(f.get("reason", "")))
            flash(request, "Key disabled." if disable else "Key enabled.")
        except BejitechError as exc:
            flash(request, str(exc), "error")
        return go(f"/inventory?id={lid}")

    # ======================= Customers =======================
    @app.get("/customers", response_class=HTMLResponse)
    def customers(request: Request, q: str = "", archived: int = 0, id: int = 0, owing: int = 0):
        ctx = ctx_of(request)
        rows = ctx.customers.list(search=q.strip(), include_archived=bool(archived))
        balances = ctx.accounts.balances()
        if owing:
            rows = [r for r in rows if balances.get(r.id, 0) > 0]
        sel = hist = acc = None
        if id:
            try:
                sel, hist, acc = ctx.customers.get(id), ctx.customers.history(id), ctx.accounts.account(id)
            except BejitechError:
                sel = None
        return page(request, "customers.html", rows=rows, q=q, archived=archived, sel=sel, hist=hist, acc=acc,
                    balances=balances, owing=owing, total_owed=sum(b for b in balances.values() if b > 0),
                    methods=[(m.value, m.label) for m in PaymentMethod], today=today_iso())

    def customer_form_view(request, cust=None, form=None, error=None, status=200, next_url=""):
        return page(request, "customer_form.html", status=status, cust=cust, form=form or {}, error=error,
                    next_url=next_url)

    @app.get("/customers/new", response_class=HTMLResponse)
    def customer_new(request: Request, next: str = ""):
        ctx_of(request)
        return customer_form_view(request, next_url=next if next.startswith("/") else "")

    @app.get("/customers/{cid}/edit", response_class=HTMLResponse)
    def customer_edit(request: Request, cid: int):
        ctx = ctx_of(request)
        c = ctx.customers.get(cid)
        return customer_form_view(request, cust=c, form={k: getattr(c, k) or "" for k in (
            "full_name", "organization", "phone", "email", "address", "notes")})

    @app.post("/customers/save", response_class=HTMLResponse)
    async def customer_save(request: Request):
        ctx = ctx_of(request)
        f = await posted(request)
        cid = _opt_int(f.get("id"))
        next_url = str(f.get("next", ""))
        try:
            new_id = ctx.customers.save(CustomerInput(
                id=cid, full_name=str(f.get("full_name", "")), organization=str(f.get("organization", "")),
                phone=str(f.get("phone", "")), email=str(f.get("email", "")), address=str(f.get("address", "")),
                notes=str(f.get("notes", ""))))
        except BejitechError as exc:
            return customer_form_view(request, cust=ctx.customers.get(cid) if cid else None, form=dict(f),
                                      error=str(exc), status=400, next_url=next_url)
        flash(request, "Customer saved.")
        if next_url.startswith("/sales/new"):
            return go(f"/sales/new?customer={new_id}")
        return go(f"/customers?id={new_id}")

    @app.post("/customers/{cid}/archive")
    async def customer_archive(request: Request, cid: int):
        ctx = ctx_of(request)
        f = await posted(request)
        archive = f.get("archived") == "1"
        try:
            ctx.customers.set_archived(cid, archive)
            flash(request, "Customer archived." if archive else "Customer restored.")
        except BejitechError as exc:
            flash(request, str(exc), "error")
        return go("/customers")

    # ---------- customer accounts ----------
    def back_to(f, fallback: str) -> RedirectResponse:
        nxt = str(f.get("next", ""))
        return go(nxt if nxt.startswith("/") and not nxt.startswith("//") else fallback)

    @app.post("/customers/{cid}/payment")
    async def customer_payment(request: Request, cid: int):
        ctx = ctx_of(request)
        f = await posted(request)
        try:
            amount = to_minor(f.get("amount", ""), "TZS")
            ctx.accounts.record_payment(cid, amount, str(f.get("date", "")), str(f.get("method", "CASH")),
                                        str(f.get("reference", "")), str(f.get("note", "")))
            flash(request, f"Payment of {format_money(amount)} recorded. Balance owed now: "
                           f"{format_money(ctx.accounts.balance(cid))}.")
        except BejitechError as exc:
            flash(request, str(exc), "error")
        return back_to(f, f"/customers?id={cid}")

    @app.post("/customers/{cid}/opening-debt")
    async def customer_opening_debt(request: Request, cid: int):
        ctx = ctx_of(request)
        f = await posted(request)
        try:
            amount = to_minor(f.get("amount", ""), "TZS")
            ctx.accounts.add_opening_debt(cid, amount, str(f.get("date", "")), str(f.get("note", "")))
            flash(request, f"Earlier debt of {format_money(amount)} added. Balance owed now: "
                           f"{format_money(ctx.accounts.balance(cid))}.")
        except BejitechError as exc:
            flash(request, str(exc), "error")
        return back_to(f, f"/customers?id={cid}")

    @app.post("/customers/entries/{eid}/void")
    async def customer_entry_void(request: Request, eid: int):
        ctx = ctx_of(request)
        f = await posted(request)
        try:
            ctx.accounts.void_entry(eid, str(f.get("reason", "")))
            flash(request, "Entry cancelled. It stays on the statement, crossed out.")
        except BejitechError as exc:
            flash(request, str(exc), "error")
        return back_to(f, "/customers")

    @app.post("/sales/{sid}/mark-paid")
    async def sale_mark_paid(request: Request, sid: int):
        ctx = ctx_of(request)
        f = await posted(request)
        try:
            if ctx.accounts.pay_sale_in_full(sid, str(f.get("date", "")) or None, str(f.get("method", "")) or None,
                                             str(f.get("reference", ""))) is None:
                flash(request, "Nothing is owed on this sale.")
            else:
                flash(request, "Payment recorded: the sale is now fully paid.")
        except BejitechError as exc:
            flash(request, str(exc), "error")
        return back_to(f, f"/sales?id={sid}")

    # ======================= New sale =======================
    @app.get("/sales/new", response_class=HTMLResponse)
    def sale_new(request: Request, customer: int = 0, product: int = 0):
        ctx = ctx_of(request)
        return page(request, "new_sale.html", customers=ctx.customers.list(),
                    products=ctx.catalogue.list_products(), customer=customer, product=product,
                    methods=[(m.value, m.label) for m in PaymentMethod], today=today_iso(), form={}, error=None,
                    balances=ctx.accounts.balances())

    @app.get("/api/recommend")
    def api_recommend(request: Request, customer: int = 0, product: int = 0, qty: int = 1):
        ctx = ctx_of(request)
        if not (customer and product and qty > 0):
            return JSONResponse({"options": [], "message": "Choose a customer and a product."})
        try:
            rec = ctx.allocation.recommend(product, qty, customer)
        except BejitechError as exc:
            return JSONResponse({"options": [], "message": str(exc)})
        opts = []
        if rec.is_possible:
            def after(plan):
                return "; ".join(f"{o.inventory_ref} will have {o.remaining - take} activation(s) left"
                                 + (" (fully allocated)" if o.remaining - take == 0 else "") for o, take in plan)
            text = " + ".join(f"{o.inventory_ref} ({o.masked_key[-5:]}) ×{o.take}, {o.remaining} left"
                              for o in rec.plan)
            opts.append({"plan": ",".join(f"{o.license_id}:{o.take}" for o in rec.plan), "recommended": True,
                         "label": f"Recommended: {text}", "reason": rec.plan[0].reason,
                         "after": after([(o, o.take) for o in rec.plan])})
            for o in rec.alternatives:
                opts.append({"plan": f"{o.license_id}:{qty}", "recommended": False,
                             "label": f"{o.inventory_ref} ({o.masked_key[-5:]}): {o.remaining} left"
                                      + (f", expires {o.expiration_date}" if o.expiration_date else ""),
                             "reason": "", "after": after([(o, qty)])})
            return JSONResponse({"options": opts, "message": ""})
        return JSONResponse({"options": [], "message": (
            f"Not enough activations available for this customer: {rec.total_available} available, "
            f"{qty} requested. Add licence keys in License Inventory.")})

    @app.post("/sales/new", response_class=HTMLResponse)
    async def sale_create(request: Request):
        ctx = ctx_of(request)
        f = await posted(request)
        try:
            customer_id, product_id = _int(f.get("customer")), _int(f.get("product"))
            if not customer_id:
                raise ValidationError("Please choose a customer.")
            plan_text = str(f.get("plan", ""))
            plan = None
            if plan_text:
                plan = [(int(a), int(b)) for a, b in (x.split(":") for x in plan_text.split(",") if x)]
            if not plan:
                raise ValidationError("Please choose which licence key to use.")
            unit = to_minor(f.get("price", ""), "TZS")
            disc = to_minor(f.get("discount", ""), "TZS")
            total_due = _int(f.get("qty"), 1) * unit - disc
            pay_status = str(f.get("pay_status", "full"))
            if pay_status == "later":
                paid_now = 0
            elif pay_status == "part":
                paid_now = to_minor(f.get("paid_now", ""), "TZS")
                if paid_now <= 0:
                    raise ValidationError("Enter the amount the customer paid now, or choose Not paid yet.")
            else:
                paid_now = max(total_due, 0)
            sale_id = ctx.sales.create_sale(SaleInput(
                customer_id=customer_id, product_id=product_id, quantity=_int(f.get("qty"), 1),
                unit_price_minor=to_minor(f.get("price", ""), "TZS"),
                discount_minor=to_minor(f.get("discount", ""), "TZS"),
                payment_method=str(f.get("payment", "MOBILE_MONEY")),
                payment_reference=str(f.get("pay_ref", "")), sale_date=str(f.get("sale_date") or today_iso()),
                notes=str(f.get("notes", "")), plan=plan, paid_now_minor=paid_now))
        except (BejitechError, ValueError) as exc:
            return page(request, "new_sale.html", status=400, customers=ctx.customers.list(),
                        products=ctx.catalogue.list_products(), customer=_int(f.get("customer")),
                        product=_int(f.get("product")), methods=[(m.value, m.label) for m in PaymentMethod],
                        today=today_iso(), form=dict(f), error=str(exc), balances=ctx.accounts.balances())
        sale = ctx.sales.get_sale(sale_id)
        try:
            ctx.delivery_notes.generate_for_sale(sale_id)
            note = f"Delivery note {sale.delivery_note_number} created."
        except BejitechError:
            note = "The delivery note could not be generated; open Delivery Notes to retry."
        owed = ctx.accounts.balance(sale.customer_id)
        flash(request, f"{sale.sales_ref} saved: {sale.customer_name}, {sale.product_names} × {sale.quantity}, "
                       f"{format_money(sale.total_minor)}. {note} "
                       + (f"{sale.customer_name} now owes {format_money(owed)} in total." if owed > 0
                          else "Fully paid."))
        return go(f"/sales?id={sale_id}")

    # ======================= Sales history =======================
    def sales_filters(request: Request) -> dict:
        qp = request.query_params
        return {"q": qp.get("q", ""), "status": qp.get("status", ""), "payment": qp.get("payment", ""),
                "date_from": qp.get("from", ""), "date_to": qp.get("to", ""), "paid": qp.get("paid", "")}

    def sales_rows(ctx, flt):
        return ctx.sales.list_sales(search=flt["q"].strip(), date_from=flt["date_from"] or None,
                                    date_to=flt["date_to"] or None, status=flt["status"] or None,
                                    payment_method=flt["payment"] or None)

    @app.get("/sales", response_class=HTMLResponse)
    def sales(request: Request, id: int = 0):
        ctx = ctx_of(request)
        flt = sales_filters(request)
        rows = sales_rows(ctx, flt)
        pay = ctx.accounts.sale_states({r.customer_id for r in rows})
        if flt["paid"] == "owed":
            rows = [r for r in rows if r.id in pay and pay[r.id].due_minor > 0]
        elif flt["paid"] == "paid":
            rows = [r for r in rows if r.id in pay and pay[r.id].due_minor <= 0]
        sel = None
        if id:
            try:
                sel = ctx.sales.get_sale(id)
            except BejitechError:
                sel = None
        if sel and sel.customer_id not in {r.customer_id for r in rows}:
            pay.update(ctx.accounts.sale_states({sel.customer_id}))
        qs = urlencode({k: v for k, v in (("q", flt["q"]), ("status", flt["status"]), ("payment", flt["payment"]),
                                          ("from", flt["date_from"]), ("to", flt["date_to"]), ("paid", flt["paid"]))
                        if v})
        return page(request, "sales.html", rows=rows, flt=flt, sel=sel, query=qs, pay=pay, today=today_iso(),
                    owed=sum(pay[r.id].due_minor for r in rows if r.id in pay and pay[r.id].due_minor > 0),
                    methods=[(m.value, m.label) for m in PaymentMethod],
                    total=sum(r.total_minor for r in rows if r.status == "COMPLETED"))

    @app.get("/sales.csv")
    def sales_csv(request: Request):
        ctx = ctx_of(request)
        from bejitech.core.dto import Report
        rows = sales_rows(ctx, sales_filters(request))
        rep = Report("Sales history", "", ["Ref", "Date", "Customer", "Product", "Qty", "Subtotal (TZS)",
                                            "Discount (TZS)", "Total (TZS)", "Payment", "Reference", "Status"],
                     [[r.sales_ref, r.sale_date, r.customer_name, r.product_names, r.quantity,
                       r.subtotal_minor, r.discount_minor, r.total_minor, PaymentMethod(r.payment_method).label,
                       r.payment_reference or "", r.status.title()] for r in rows])
        return _csv_response(rep, "Sales history.csv")

    @app.post("/sales/allocations/{aid}/confirm")
    async def allocation_confirm(request: Request, aid: int):
        ctx = ctx_of(request)
        f = await posted(request)
        try:
            ctx.allocation.confirm(aid)
            flash(request, "Activation confirmed.")
        except BejitechError as exc:
            flash(request, str(exc), "error")
        return go(f"/sales?id={_int(f.get('sale_id'))}")

    @app.get("/sales/{sid}/cancel", response_class=HTMLResponse)
    def sale_cancel_form(request: Request, sid: int, not_delivered: int = 0):
        ctx = ctx_of(request)
        sale = ctx.sales.get_sale(sid)
        opts = ctx.sales.cancellation_options(sid, key_not_delivered=bool(not_delivered))
        return page(request, "cancel_sale.html", sale=sale, opts=opts, not_delivered=not_delivered, error=None,
                    reason="")

    @app.post("/sales/{sid}/cancel", response_class=HTMLResponse)
    async def sale_cancel(request: Request, sid: int):
        ctx = ctx_of(request)
        f = await posted(request)
        nd = bool(f.get("not_delivered"))
        release = {int(x) for x in f.getlist("release") if str(x).isdigit()}
        try:
            ctx.sales.cancel_sale(sid, str(f.get("reason", "")), release_allocation_ids=release,
                                  key_not_delivered=nd)
        except BejitechError as exc:
            return page(request, "cancel_sale.html", status=400, sale=ctx.sales.get_sale(sid),
                        opts=ctx.sales.cancellation_options(sid, key_not_delivered=nd), not_delivered=int(nd),
                        error=str(exc), reason=str(f.get("reason", "")))
        flash(request, "Sale cancelled.")
        return go(f"/sales?id={sid}")

    # ======================= Delivery notes =======================
    @app.get("/delivery-notes", response_class=HTMLResponse)
    def delivery_notes(request: Request, q: str = "", id: int = 0):
        ctx = ctx_of(request)
        rows = ctx.delivery_notes.list_notes(search=q.strip())
        sel = next((n for n in rows if n.id == id), None)
        mail = None
        if sel:
            try:
                mail = ctx.delivery_notes.email_draft(sel.id)["url"]
            except BejitechError:
                mail = None
        return page(request, "delivery_notes.html", rows=rows, q=q, sel=sel, mail=mail)

    @app.get("/delivery-notes/{nid}/pdf")
    def delivery_note_pdf(request: Request, nid: int, download: int = 0):
        ctx = ctx_of(request)
        try:
            path = ctx.delivery_notes.pdf_file(nid)
        except BejitechError:
            return Response(status_code=404)
        disp = "attachment" if download else "inline"
        return FileResponse(path, media_type="application/pdf",
                            headers={"Content-Disposition": f'{disp}; filename="{path.name}"'})

    @app.post("/delivery-notes/{nid}/reissue")
    async def delivery_note_reissue(request: Request, nid: int):
        ctx = ctx_of(request)
        await posted(request)
        try:
            new_id = ctx.delivery_notes.new_revision(nid)
            flash(request, "New delivery note issued; the old one is marked VOID.")
            return go(f"/delivery-notes?id={new_id}")
        except BejitechError as exc:
            flash(request, str(exc), "error")
            return go(f"/delivery-notes?id={nid}")

    # ======================= Reports =======================
    @app.get("/reports", response_class=HTMLResponse)
    def reports(request: Request, name: str = "inventory", period: str = "all"):
        ctx = ctx_of(request)
        name = name if name in dict(REPORTS) else "inventory"
        period = period if period in PERIODS else "all"
        rep = ctx.reports.report(name, *period_range(period))
        return page(request, "reports.html", rep=rep, rname=name, period=period, reports=REPORTS,
                    periods=PERIODS, dated=name in ("sales", "customers", "profit"), money_cols=MONEY_COLS)

    @app.get("/reports/{name}.{fmt}")
    def report_export(request: Request, name: str, fmt: str, period: str = "all"):
        ctx = ctx_of(request)
        if name not in dict(REPORTS) or fmt not in ("csv", "pdf"):
            return Response(status_code=404)
        rep = ctx.reports.report(name, *period_range(period if period in PERIODS else "all"))
        fname = f"{rep.title}.{fmt}"
        if fmt == "csv":
            return _csv_response(rep, fname)
        from bejitech.pdf.report_pdf import write_report_pdf
        tmp = Path(tempfile.mkdtemp()) / fname
        write_report_pdf(tmp, rep, ctx.settings.seller().get("name", ""))
        return FileResponse(tmp, media_type="application/pdf",
                            headers={"Content-Disposition": f'attachment; filename="{fname}"'})

    # ======================= Backup & restore =======================
    def backups_supported() -> bool:
        return not state.db.is_postgres

    def restore_supported() -> bool:
        return backups_supported() and not (type(state.keystore) is EnvKeyStore)

    @app.get("/backup", response_class=HTMLResponse)
    def backup(request: Request):
        ctx = ctx_of(request)
        hist = ctx.backup.history() if backups_supported() else []
        for h in hist:
            h["name"] = Path(h["file_path"]).name
            h["downloadable"] = (state.paths.backups / h["name"]).exists()
        return page(request, "backup.html", hist=hist, supported=backups_supported(),
                    restore_ok=restore_supported(), folder=str(state.paths.backups), error=None)

    @app.post("/backup/create")
    async def backup_create(request: Request):
        ctx = ctx_of(request)
        f = await posted(request)
        try:
            if str(f.get("password", "")) != str(f.get("password2", "")):
                raise ValidationError("The two backup passwords do not match.")
            path = ctx.backup.create_backup(state.paths.backups, str(f.get("password", "")))
            flash(request, f"Backup created and verified: {path.name}. Download it and keep a copy off this "
                           "computer (USB drive, Google Drive…).")
        except BejitechError as exc:
            flash(request, str(exc), "error")
        return go("/backup")

    @app.get("/backup/file/{name}")
    def backup_file(request: Request, name: str):
        ctx_of(request)
        if not re.fullmatch(r"[A-Za-z0-9_.\-]+", name):
            return Response(status_code=404)
        path = state.paths.backups / name
        if not path.is_file():
            return Response(status_code=404)
        return FileResponse(path, media_type="application/octet-stream",
                            headers={"Content-Disposition": f'attachment; filename="{name}"'})

    @app.post("/backup/restore")
    async def backup_restore(request: Request):
        ctx = ctx_of(request)
        f = await posted(request)
        upload = f.get("file")
        if not restore_supported():
            flash(request, "Restoring is not available on this server.", "error")
            return go("/backup")
        if upload is None or not getattr(upload, "filename", ""):
            flash(request, "Choose a backup file first.", "error")
            return go("/backup")
        if f.get("confirm") != "REPLACE":
            flash(request, "Type REPLACE to confirm that all current data will be replaced.", "error")
            return go("/backup")
        tmp = state.paths.backups / f"upload_{int(time.time())}.bjtbackup"
        tmp.write_bytes(await upload.read())
        try:
            safety = ctx.backup.restore_backup(tmp, str(f.get("password", "")))
        except BejitechError as exc:
            state.reset_database()
            flash(request, str(exc), "error")
            return go("/backup")
        finally:
            tmp.unlink(missing_ok=True)
        state.reset_database()
        request.session.clear()
        request.session["flash"] = [["ok", f"Backup restored (a safety copy of the previous data was saved as "
                                           f"{safety.name}). Sign in with the account from the backup."]]
        return go("/login")

    # ======================= Settings =======================
    @app.get("/settings", response_class=HTMLResponse)
    def settings(request: Request, tab: str = "business", q: str = ""):
        ctx = ctx_of(request)
        tab = tab if tab in dict(SETTINGS_TABS) else "business"
        audit = ctx.audit.recent(limit=300, search=q.strip()) if tab == "audit" else []
        return page(request, "settings.html", tab=tab, tabs=SETTINGS_TABS, s=ctx.settings.all(),
                    types=ctx.catalogue.list_license_types() if tab == "types" else [], audit=audit, q=q,
                    keystore=state.keystore.describe(), two_step=ui.config.two_step, data_dir=str(state.paths.root),
                    database="PostgreSQL" if state.db.is_postgres else str(state.paths.database))

    SETTING_FIELDS = {
        "business": ["seller.name", "seller.business_name", "seller.phone", "seller.email", "seller.address"],
        "sales": ["currency.usd_rate", "inventory.default_low_stock"],
        "delivery": ["delivery.include_signature", "delivery.show_balance", "delivery.footer"],
        "security": ["security.autolock_minutes"],
    }

    @app.post("/settings/save")
    async def settings_save(request: Request):
        ctx = ctx_of(request)
        f = await posted(request)
        tab = str(f.get("tab", "business"))
        values = {}
        for key in SETTING_FIELDS.get(tab, []):
            if key in ("delivery.include_signature", "delivery.show_balance"):
                values[key] = "1" if f.get(key) else "0"
            else:
                values[key] = str(f.get(key, ""))
        try:
            if "currency.usd_rate" in values:
                from bejitech.core.money import parse_rate
                parse_rate(values["currency.usd_rate"])
            for k in ("inventory.default_low_stock", "security.autolock_minutes"):
                if k in values and not values[k].strip().isdigit():
                    raise ValidationError("Please enter a whole number.")
            ctx.settings.update(values)
            flash(request, "Settings saved.")
        except BejitechError as exc:
            flash(request, str(exc), "error")
        return go(f"/settings?tab={tab}")

    @app.post("/settings/types")
    async def settings_types(request: Request):
        ctx = ctx_of(request)
        f = await posted(request)
        try:
            for t in ctx.catalogue.list_license_types():
                tid = t["id"]
                ctx.catalogue.update_license_type(tid, bool(f.get(f"multi_{tid}")), bool(f.get(f"reassign_{tid}")),
                                                  _int(f.get(f"cap_{tid}"), t["default_capacity"]))
            flash(request, "Licence types saved.")
        except BejitechError as exc:
            flash(request, str(exc), "error")
        return go("/settings?tab=types")

    @app.post("/settings/password")
    async def settings_password(request: Request):
        ctx = ctx_of(request)
        f = await posted(request)
        try:
            if str(f.get("new1", "")) != str(f.get("new2", "")):
                raise ValidationError("The new passwords do not match.")
            ctx.auth.change_password(str(f.get("current", "")), str(f.get("new1", "")))
            flash(request, "Password changed.")
        except BejitechError as exc:
            flash(request, str(exc), "error")
        return go("/settings?tab=security")

    @app.post("/settings/recovery")
    async def settings_recovery(request: Request):
        ctx = ctx_of(request)
        f = await posted(request)
        try:
            if str(f.get("new1", "")) != str(f.get("new2", "")):
                raise ValidationError("The new passphrases do not match.")
            ctx.auth.change_recovery_passphrase(str(f.get("current", "")), str(f.get("new1", "")))
            flash(request, "Recovery passphrase changed. Write the new one down and keep it safe.")
        except BejitechError as exc:
            flash(request, str(exc), "error")
        return go("/settings?tab=security")

    @app.get("/healthz/consistency")
    def consistency(request: Request):
        ctx = ctx_of(request)
        return JSONResponse({"problems": ctx.inventory.verify_consistency()})

    _ = (EnvFileKeyStore, convert_to_tzs)  # imported for templates/tests


def _csv_response(rep, filename: str) -> Response:
    from bejitech.exports.csv_export import write_csv
    tmp = Path(tempfile.mkdtemp()) / "export.csv"
    write_csv(tmp, rep)
    return Response(tmp.read_bytes(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})
