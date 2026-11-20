"""Database engine and transaction handling.

Two back-ends share the same models and services:

* SQLite (desktop app): a file path. Each unit of work starts with BEGIN IMMEDIATE.
* PostgreSQL (web app): a ``postgresql://`` URL. Each unit of work takes the same
  application-wide lock with ``pg_advisory_xact_lock``, so the services keep the exact
  one-writer-at-a-time guarantee they were written and tested for (rules R2 and R3).
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

# Any constant works; it only has to be the same for every connection of this app.
PG_LOCK_ID = 0x42454A49  # "BEJI"


def is_postgres_url(target: str | Path) -> bool:
    return isinstance(target, str) and target.startswith(("postgresql://", "postgres://", "postgresql+psycopg://"))


def normalize_pg_url(url: str) -> str:
    """Render and Heroku-style URLs use postgres:// ; SQLAlchemy wants postgresql+psycopg://."""
    for prefix in ("postgresql+psycopg://", "postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


class Database:
    def __init__(self, target: Path | str):
        if is_postgres_url(target):
            self.dialect = "postgresql"
            self.path = None
            self.url = normalize_pg_url(str(target))
            self.engine = create_engine(self.url, future=True, pool_pre_ping=True,
                                        pool_size=5, max_overflow=5)

            @event.listens_for(self.engine, "begin")
            def _on_begin_pg(conn):
                conn.exec_driver_sql(f"SELECT pg_advisory_xact_lock({PG_LOCK_ID})")
        else:
            self.dialect = "sqlite"
            self.path = Path(target)
            self.url = f"sqlite:///{self.path}"
            self.engine = create_engine(self.url, future=True)

            @event.listens_for(self.engine, "connect")
            def _on_connect(dbapi_conn, _record):
                # Let SQLAlchemy control transactions; we issue BEGIN IMMEDIATE ourselves
                dbapi_conn.isolation_level = None
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA foreign_keys = ON")
                cur.execute("PRAGMA busy_timeout = 5000")
                cur.close()

            @event.listens_for(self.engine, "begin")
            def _on_begin(conn):
                # Take the write lock up-front so two writers can never interleave
                conn.exec_driver_sql("BEGIN IMMEDIATE")

        self._factory = sessionmaker(self.engine, expire_on_commit=False)

    @property
    def is_postgres(self) -> bool:
        return self.dialect == "postgresql"

    @contextmanager
    def session(self) -> Iterator[Session]:
        """One atomic unit of work: commits on success, rolls back on any error."""
        s = self._factory()
        try:
            yield s
            s.commit()
        except BaseException:
            s.rollback()
            raise
        finally:
            s.close()

    def dispose(self) -> None:
        self.engine.dispose()
