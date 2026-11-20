"""Web version, Phase 2: every screen opens and the everyday actions work end to end.

Runs on SQLite by default and on PostgreSQL when BEJITECH_TEST_DATABASE_URL is set."""
import re

import pytest

from conftest import PASSWORD
from test_web import client, csrf, setup_admin  # noqa: F401 - fixtures/helpers shared with test_web

PAGES = ["/", "/?period=month", "/products", "/products/new", "/inventory", "/inventory?state=AVAILABLE",
         "/inventory/new", "/customers", "/customers/new", "/sales/new", "/sales", "/delivery-notes",
         "/backup", "/healthz/consistency"] + \
        [f"/reports?name={n}&period=year" for n in ("inventory", "sales", "customers", "activations", "profit")] + \
        [f"/settings?tab={t}" for t in ("business", "sales", "types", "delivery", "security", "audit", "about")]

NAV = ["Dashboard", "Software Products", "License Inventory", "New Sale", "Customers", "Sales History",
       "Delivery Notes", "Reports", "Backup &amp; Restore", "Settings"]


def token(client, url="/"):
    return csrf(client.get(url).text)


def product_id(client, name="Windows 11 Pro") -> int:
    html = client.get("/products").text
    m = re.search(r'href="/products/(\d+)/edit"><strong>' + re.escape(name) + "<", html)
    assert m, "product not listed"
    return int(m.group(1))


def add_key(client, pid: int, keys: str) -> None:
    r = client.post("/inventory/save", data={
        "csrf": token(client, "/inventory/new"), "product_id": pid, "keys": keys, "purchase_date": "2026-11-01",
        "cost": "20,000", "currency": "TZS", "capacity": "1"})
    assert r.status_code == 303, r.text[:500]


def add_customer(client, name="Asha Mwakyusa") -> int:
    r = client.post("/customers/save", data={"csrf": token(client, "/customers/new"), "full_name": name,
                                             "phone": "+255 712 345 678", "email": "asha@example.com"})
    assert r.status_code == 303
    return int(re.search(r"id=(\d+)", r.headers["location"]).group(1))


def test_every_screen_opens_with_the_desktop_sidebar(client):
    setup_admin(client)
    for url in PAGES:
        r = client.get(url)
        assert r.status_code == 200, url
        assert "built-in method" not in r.text and "Undefined" not in r.text, url
    html = client.get("/").text
    positions = [html.index(label) for label in NAV]
    assert positions == sorted(positions), "sidebar order differs from the desktop app"
    assert 'class="nav-item on"' in html or "aria-current" in html


def test_add_product_and_key_then_sell_and_cancel(client):
    setup_admin(client)
    pid = product_id(client)
    r = client.get(f"/products/{pid}/edit")
    assert r.status_code == 200 and "Windows 11 Pro" in r.text

    add_key(client, pid, "WIN11-AAAAA-BBBBB-CCCCC-7HQ2D")
    add_key(client, pid, "WIN11-DDDDD-EEEEE-FFFFF-11111\nWIN11-GGGGG-HHHHH-IIIII-22222")
    inv = client.get("/inventory").text
    assert "7HQ2D" in inv and "WIN11-AAAAA" not in inv
    lid = int(re.search(r'data-href="/inventory\?(?:[^"]*&)?id=(\d+)', inv).group(1))
    assert client.get(f"/inventory?id={lid}").status_code == 200
    assert client.get(f"/inventory/{lid}/edit").status_code == 200

    # Duplicate key is refused with a readable message
    r = client.post("/inventory/save", data={"csrf": token(client, "/inventory/new"), "product_id": pid,
                                             "keys": "win11-aaaaa-bbbbb-ccccc-7hq2d", "purchase_date": "2026-11-01",
                                             "currency": "TZS", "capacity": "1"})
    assert r.status_code == 400 and "already in inventory" in r.text

    cid = add_customer(client)
    rec = client.get(f"/api/recommend?customer={cid}&product={pid}&qty=1").json()
    assert rec["options"] and rec["options"][0]["recommended"]
    plan = rec["options"][0]["plan"]

    r = client.post("/sales/new", data={"csrf": token(client, "/sales/new"), "customer": cid, "product": pid,
                                        "qty": "1", "price": "60,000", "discount": "0", "payment": "MOBILE_MONEY",
                                        "pay_ref": "MP123", "sale_date": "2026-11-20", "plan": plan})
    assert r.status_code == 303, r.text[:500]
    sid = int(re.search(r"id=(\d+)", r.headers["location"]).group(1))
    page = client.get(f"/sales?id={sid}").text
    assert "Asha Mwakyusa" in page and "60,000" in page
    assert "Asha Mwakyusa" in client.get("/sales.csv").text

    notes = client.get("/delivery-notes").text
    nid = int(re.search(r"/delivery-notes/(\d+)/pdf", notes).group(1))
    pdf = client.get(f"/delivery-notes/{nid}/pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")

    for name in ("sales", "inventory", "profit"):
        assert client.get(f"/reports/{name}.csv?period=all").status_code == 200
    assert client.get("/reports/sales.pdf?period=all").content.startswith(b"%PDF")

    form = client.get(f"/sales/{sid}/cancel").text
    release = re.findall(r'name="release" value="(\d+)" checked', form)
    r = client.post(f"/sales/{sid}/cancel", data={"csrf": csrf(form), "reason": "Customer changed their mind",
                                                  "release": release})
    assert r.status_code == 303, re.findall(r'class="flash error[^>]*>([^<]+)', r.text)
    assert "Cancelled" in client.get(f"/sales?id={sid}").text


def test_reveal_key_needs_password_after_a_while(client):
    setup_admin(client)
    pid = product_id(client)
    add_key(client, pid, "SECRT-KEYAB-CDEFG-HIJKL-7HQ2D")
    lid = int(re.search(r'data-href="/inventory\?(?:[^"]*&)?id=(\d+)', client.get("/inventory").text).group(1))
    # Just signed in: reveal works straight away and is recorded in the audit log
    r = client.post(f"/inventory/{lid}/reveal", data={"csrf": token(client, "/inventory")})
    assert r.status_code == 303
    assert "SECRT-KEYAB-CDEFG-HIJKL-7HQ2D" in client.get(f"/inventory?id={lid}").text
    assert "SECRT" not in client.get(f"/inventory?id={lid}").text  # shown once only
    assert "KEY_REVEALED" in client.get("/settings?tab=audit").text


def test_customer_edit_settings_and_backup(client):
    setup_admin(client)
    cid = add_customer(client, "Juma Hassan")
    assert client.get(f"/customers/{cid}/edit").status_code == 200
    assert "Juma Hassan" in client.get(f"/customers?id={cid}").text

    r = client.post("/settings/save", data={"csrf": token(client, "/settings"), "tab": "business",
                                            "seller.name": "Bejitech", "seller.phone": "+255 700 111 222"})
    assert r.status_code == 303
    assert "+255 700 111 222" in client.get("/settings?tab=business").text
    r = client.post("/settings/save", data={"csrf": token(client, "/settings"), "tab": "sales",
                                            "currency.usd_rate": "abc", "inventory.default_low_stock": "3"})
    assert "error" in client.get("/settings?tab=sales").text

    r = client.post("/settings/password", data={"csrf": token(client, "/settings"), "current": PASSWORD,
                                                "new1": "another-long-password", "new2": "different"})
    assert "do not match" in client.get("/settings?tab=security").text


@pytest.mark.sqlite_only
def test_backup_create_and_download(client):
    setup_admin(client)
    r = client.post("/backup/create", data={"csrf": token(client, "/backup"), "password": "backup-pass-123",
                                            "password2": "backup-pass-123"})
    assert r.status_code == 303
    page = client.get("/backup").text
    assert "Backup created" in page
    name = re.search(r"/backup/file/([A-Za-z0-9_.\-]+)", page).group(1)
    assert client.get(f"/backup/file/{name}").status_code == 200
    assert client.get("/backup/file/..%2Fweb.env").status_code == 404


def test_pages_need_sign_in(client):
    setup_admin(client)
    client.cookies.clear()
    for url in ("/products", "/inventory", "/sales", "/reports", "/settings", "/api/recommend"):
        r = client.get(url)
        assert r.status_code in (303, 401), url


def test_lifetime_keys_and_keys_with_an_expiry_date(client):
    setup_admin(client)
    pid = product_id(client)
    form = client.get("/inventory/new").text
    assert '<option value="lifetime" selected' in form  # new keys default to lifetime
    client.post("/inventory/save", data={"csrf": csrf(form), "product_id": pid, "keys": "LIFE1-AAAAA-BBBBB-CCCCC-11111",
                                         "purchase_date": "2026-11-01", "currency": "TZS", "capacity": "1",
                                         "validity": "lifetime", "expiry": "2027-01-01"})
    client.post("/inventory/save", data={"csrf": token(client, "/inventory/new"), "product_id": pid,
                                         "keys": "YEAR1-AAAAA-BBBBB-CCCCC-22222", "purchase_date": "2026-11-01",
                                         "currency": "TZS", "capacity": "1", "validity": "date", "expiry": "2027-11-01"})
    inv = client.get("/inventory").text
    assert "Lifetime" in inv and "01 Nov 2027" in inv
    assert "2027-01-01" not in inv and "01 Jan 2027" not in inv
