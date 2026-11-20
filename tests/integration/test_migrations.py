import sqlite3

import pytest
from sqlalchemy import inspect

from bejitech.db.migrations import LATEST_VERSION, MigrationError, migrate
from bejitech.db.models import Base

pytestmark = pytest.mark.sqlite_only


def test_fresh_migration_and_seed(raw_ctx):
    conn = sqlite3.connect(raw_ctx.paths.database)
    names = [r[0] for r in conn.execute("SELECT display_name FROM products ORDER BY id")]
    assert names == ["Microsoft Office 2019 Professional Plus", "Microsoft Office 2021 Professional Plus",
                     "Microsoft Office 2024 Professional Plus", "Windows 11 Pro"]
    assert conn.execute("SELECT value FROM settings WHERE key='seller.name'").fetchone()[0] == "Christian Joel Mtei"


def test_migrate_is_idempotent(raw_ctx):
    assert migrate(raw_ctx.paths.database) == LATEST_VERSION


def test_orm_models_match_database(raw_ctx):
    insp = inspect(raw_ctx.db.engine)
    for table in Base.metadata.sorted_tables:
        db_cols = {c["name"] for c in insp.get_columns(table.name)}
        orm_cols = {c.name for c in table.columns}
        assert orm_cols == db_cols, table.name


def test_newer_database_refused(raw_ctx):
    conn = sqlite3.connect(raw_ctx.paths.database)
    conn.execute("INSERT INTO schema_version VALUES (999, 'future', 'x')")
    conn.commit()
    conn.close()
    with pytest.raises(MigrationError):
        migrate(raw_ctx.paths.database)
