import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from bejitech.config.paths import AppPaths  # noqa: E402
from bejitech.core.dto import CustomerInput, LicenseInput  # noqa: E402
from bejitech.security import passwords  # noqa: E402
from bejitech.security.keystore import MemoryKeyStore  # noqa: E402
from bejitech.services.context import AppContext  # noqa: E402

passwords.use_fast_parameters_for_tests()

PASSWORD = "correct horse 1"
RECOVERY = "my recovery passphrase"


# Set BEJITECH_TEST_DATABASE_URL=postgresql://... to run the suite against PostgreSQL
# (the web version's database). Each test starts from an empty schema.
PG_URL = os.environ.get("BEJITECH_TEST_DATABASE_URL") or None


def _reset_pg_schema(url: str) -> None:
    import psycopg
    plain = url.replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(plain, autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS public CASCADE")
        conn.execute("CREATE SCHEMA public")


def pytest_configure(config):
    config.addinivalue_line("markers", "sqlite_only: test reads the SQLite file directly")


def pytest_collection_modifyitems(config, items):
    if PG_URL:
        skip = pytest.mark.skip(reason="SQLite file only (desktop app)")
        for item in items:
            if "sqlite_only" in item.keywords:
                item.add_marker(skip)


@pytest.fixture
def paths(tmp_path) -> AppPaths:
    if PG_URL:
        _reset_pg_schema(PG_URL)
    return AppPaths(root=tmp_path / "data", logs=tmp_path / "logs", database_url=PG_URL).ensure()


def raw_execute(ctx, sql: str):
    """Run SQL straight against the database, bypassing every service (both back-ends)."""
    from sqlalchemy import text
    with ctx.db.engine.connect() as conn:
        result = conn.execute(text(sql))
        rows = result.fetchall() if result.returns_rows else None
        conn.commit()
        return rows


@pytest.fixture
def keystore():
    return MemoryKeyStore()


@pytest.fixture
def raw_ctx(paths, keystore) -> AppContext:
    ctx = AppContext.open(paths, keystore)
    yield ctx
    ctx.db.dispose()


@pytest.fixture
def ctx(raw_ctx) -> AppContext:
    raw_ctx.auth.create_admin("Christian Joel Mtei", "admin", PASSWORD, RECOVERY)
    return raw_ctx


def product_id(ctx, name="Microsoft Office 2024 Professional Plus") -> int:
    return next(p.id for p in ctx.catalogue.list_products() if p.display_name == name)


def add_key(ctx, key="ABCDE-FGHIJ-KLMNO-PQRST-UVWXY", capacity=1, product=None, **kw) -> int:
    data = LicenseInput(product_id=product or product_id(ctx), license_key=key, purchase_date=kw.pop("purchase_date", "2026-11-01"),
                        purchase_cost_minor=kw.pop("cost", 30000), permitted_capacity=capacity, **kw)
    return ctx.inventory.add_license(data)


def add_customer(ctx, name="Amina Hassan", **kw) -> int:
    return ctx.customers.save(CustomerInput(full_name=name, **kw))


@pytest.fixture
def helpers():
    class H:
        pass
    h = H()
    h.product_id, h.add_key, h.add_customer = product_id, add_key, add_customer
    return h
