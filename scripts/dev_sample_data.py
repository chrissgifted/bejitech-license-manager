"""Fill a SEPARATE demo data folder with example keys, customers and sales so you can try the app.

    BEJITECH_DATA_DIR=~/BejitechDemo python scripts/dev_sample_data.py
    BEJITECH_DATA_DIR=~/BejitechDemo python run.py        (sign in: admin / demo-password)

Refuses to run against a folder that already has data. Never point it at your real data folder.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bejitech.config.paths import default_paths  # noqa: E402
from bejitech.core.dto import CustomerInput, LicenseInput, SaleInput  # noqa: E402
from bejitech.security.keystore import default_keystore  # noqa: E402
from bejitech.services.context import AppContext  # noqa: E402


def main():
    if not os.environ.get("BEJITECH_DATA_DIR"):
        sys.exit("Set BEJITECH_DATA_DIR to an empty demo folder first (see the docstring).")
    paths = default_paths().ensure()
    ctx = AppContext.open(paths, default_keystore(paths.root))
    if ctx.auth.has_users():
        sys.exit("That folder already contains data. Choose an empty folder.")
    ctx.auth.create_admin("Christian Joel Mtei", "admin", "demo-password", "demo recovery passphrase")
    ctx.settings.update({"seller.phone": "+255 700 000 000", "seller.email": "sales@example.com"})
    products = {p.display_name: p.id for p in ctx.catalogue.list_products()}
    prices = {"Microsoft Office 2019 Professional Plus": 45000, "Microsoft Office 2021 Professional Plus": 65000,
              "Microsoft Office 2024 Professional Plus": 85000, "Windows 11 Pro": 60000}
    from bejitech.core.dto import ProductInput
    for name, price in prices.items():
        p = ctx.catalogue.get_product(products[name])
        ctx.catalogue.save_product(ProductInput(
            id=p.id, publisher_name=p.publisher, category_name=p.category, product_line_name=p.product_line,
            version=p.version, edition=p.edition, license_type_id=p.license_type_id, display_name=p.display_name,
            selling_price_minor=price, download_url=p.download_url or "https://example.com/download",
            download_label=p.download_label, installation_instructions=p.installation_instructions,
            activation_instructions=p.activation_instructions, low_stock_threshold=3))
    n = 0
    for name, (count, cap, cost) in {"Microsoft Office 2024 Professional Plus": (4, 5, 1200),
                                     "Microsoft Office 2021 Professional Plus": (2, 1, 25000),
                                     "Microsoft Office 2019 Professional Plus": (3, 1, 18000),
                                     "Windows 11 Pro": (3, 1, 22000)}.items():
        for _ in range(count):
            n += 1
            usd = cap > 1
            ctx.inventory.add_license(LicenseInput(
                product_id=products[name], license_key=f"DEMO{n:01d}-AB12C-DE34F-GH56J-K{n:04d}",
                purchase_date="2026-10-0" + str(1 + n % 9), purchase_cost_minor=cost,
                purchase_currency="USD" if usd else "TZS", exchange_rate_to_tzs="2650",
                permitted_capacity=cap, supplier_name="Demo Supplier Ltd", allows_multiple_customers=usd))
    customers = [ctx.customers.save(CustomerInput(full_name=nm, organization=org, phone=ph, email=em))
                 for nm, org, ph, em in [("Amina Hassan", None, "+255 712 000 001", "amina@example.com"),
                                         ("Joseph Mrema", "Kilimo Ltd", "+255 754 000 002", "joseph@example.com"),
                                         ("Neema Swai", "Swai Consulting", "+255 765 000 003", None)]]
    for cust, name, qty, day in [(0, "Microsoft Office 2024 Professional Plus", 1, "2026-11-03"),
                                 (1, "Microsoft Office 2024 Professional Plus", 3, "2026-11-08"),
                                 (2, "Windows 11 Pro", 1, "2026-11-12"),
                                 (1, "Microsoft Office 2021 Professional Plus", 1, "2026-11-15")]:
        sid = ctx.sales.create_sale(SaleInput(customers[cust], products[name], qty, prices[name], "MOBILE_MONEY", day))
        ctx.delivery_notes.generate_for_sale(sid)
    print(f"Demo data created in {paths.root}. Sign in with admin / demo-password")


if __name__ == "__main__":
    main()
