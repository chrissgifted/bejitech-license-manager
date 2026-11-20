"""Initial data inserted by migration 0001."""
from __future__ import annotations

import sqlite3
import uuid

from bejitech.core.timeutil import utcnow_iso

OFFICE_INSTALL = """1. Uninstall any older or trial versions of Microsoft Office from the computer.
2. Download the installer using the download link on this delivery note.
3. Run the installer as an administrator and wait for the installation to finish.
4. Restart the computer if asked."""

OFFICE_ACTIVATE = """1. Open any Office application (for example Word).
2. Go to File > Account > Change Product Key (or Activate Product).
3. Enter the licence key shown on this delivery note and follow the prompts.
4. Make sure the computer is connected to the internet during activation."""

WINDOWS_INSTALL = """1. Back up your files before upgrading or reinstalling Windows.
2. If Windows 11 is already installed, skip to activation.
3. Otherwise download the Windows 11 installation media using the download link and follow the setup wizard."""

WINDOWS_ACTIVATE = """1. Open Settings > System > Activation.
2. Select Change product key.
3. Enter the licence key shown on this delivery note and select Next.
4. Keep the computer connected to the internet until activation is confirmed."""

CATEGORIES = [
    "Office Suites", "Operating Systems", "Servers", "Developer Tools",
    "Design & Graphics", "Security", "Other",
]

LICENSE_TYPES = [
    # code, name, description, multi-customer, reassignable, default capacity
    ("RETAIL", "Retail", "Full retail licence for one user/device.", 0, 0, 1),
    ("OEM", "OEM", "Tied to the first device it is activated on.", 0, 0, 1),
    ("MAK", "MAK (Multiple Activation Key)", "Volume key with a fixed number of activations.", 0, 0, 5),
    ("VOLUME", "Volume licence", "Organisation volume licence.", 0, 0, 5),
    ("SUBSCRIPTION", "Subscription", "Time-limited subscription.", 0, 0, 1),
    ("BIND", "Bind (account-linked)", "Linked to a customer's account once redeemed.", 0, 0, 1),
]

SETTINGS = {
    "seller.name": "Christian Joel Mtei",
    "seller.business_name": "Bejitech",
    "seller.phone": "",
    "seller.email": "",
    "seller.address": "",
    "currency.default": "TZS",
    "currency.usd_rate": "2650",
    "inventory.default_low_stock": "3",
    "security.autolock_minutes": "15",
    "security.clipboard_clear_seconds": "60",
    "delivery.include_signature": "1",
    "delivery.footer": "Thank you for your purchase. Please keep this document safe.",
}


def seed_initial(conn: sqlite3.Connection) -> None:
    """conn is a sqlite3 connection, or the PostgreSQL adapter from migrations.py."""
    now = utcnow_iso()
    u = lambda: str(uuid.uuid4())  # noqa: E731

    for key, value in SETTINGS.items():
        conn.execute("INSERT INTO settings(key, value, updated_at) VALUES (?,?,?)", (key, value, now))

    for i, name in enumerate(CATEGORIES):
        conn.execute("INSERT INTO categories(uuid, name, sort_order) VALUES (?,?,?)", (u(), name, i))

    for row in LICENSE_TYPES:
        conn.execute(
            "INSERT INTO license_types(code, name, description, allows_multiple_customers, "
            "reassignable, default_capacity) VALUES (?,?,?,?,?,?)",
            row,
        )

    conn.execute(
        "INSERT INTO publishers(uuid, name, website, created_at, updated_at) VALUES (?,?,?,?,?)",
        (u(), "Microsoft", "https://www.microsoft.com", now, now),
    )
    pub_id = conn.execute("SELECT id FROM publishers WHERE name='Microsoft'").fetchone()[0]
    cat = {r[1]: r[0] for r in conn.execute("SELECT id, name FROM categories")}
    lt = {r[1]: r[0] for r in conn.execute("SELECT id, code FROM license_types")}

    lines = {}
    for name, category in (("Microsoft Office", "Office Suites"), ("Windows", "Operating Systems")):
        conn.execute(
            "INSERT INTO product_lines(uuid, publisher_id, category_id, name, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?)",
            (u(), pub_id, cat[category], name, now, now),
        )
        lines[name] = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    products = [
        ("Microsoft Office", "Microsoft Office 2019 Professional Plus", "2019", "Professional Plus",
         None, None, OFFICE_INSTALL, OFFICE_ACTIVATE),
        ("Microsoft Office", "Microsoft Office 2021 Professional Plus", "2021", "Professional Plus",
         None, None, OFFICE_INSTALL, OFFICE_ACTIVATE),
        ("Microsoft Office", "Microsoft Office 2024 Professional Plus", "2024", "Professional Plus",
         None, None, OFFICE_INSTALL, OFFICE_ACTIVATE),
        ("Windows", "Windows 11 Pro", "11", "Pro",
         "https://www.microsoft.com/software-download/windows11", "Download Windows 11",
         WINDOWS_INSTALL, WINDOWS_ACTIVATE),
    ]
    for line, name, version, edition, url, label, install, activate in products:
        conn.execute(
            "INSERT INTO products(uuid, product_line_id, display_name, version, edition, platform, "
            "license_type_id, download_url, download_label, installation_instructions, "
            "activation_instructions, low_stock_threshold, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (u(), lines[line], name, version, edition, "Windows", lt["RETAIL"], url, label,
             install, activate, 3, now, now),
        )
