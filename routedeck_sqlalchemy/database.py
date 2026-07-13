from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from .models import Base, SchemaMigrationRow


PERSISTENCE_SCHEMA_VERSION = 3
SUPPORTED_DIALECTS = frozenset({"sqlite", "postgresql"})


class UnsupportedDatabaseDialect(ValueError):
    pass


class UnsupportedDatabaseSchema(RuntimeError):
    pass


@dataclass(frozen=True)
class DatabaseRuntime:
    engine: Engine
    session_factory: sessionmaker[Session]
    dialect_name: str
    database_url: str

    def dispose(self) -> None:
        self.engine.dispose()


def open_database(
    database_url: str,
    *,
    busy_timeout: timedelta,
) -> DatabaseRuntime:
    if busy_timeout <= timedelta(0):
        raise ValueError("busy_timeout must be positive")
    url = make_url(database_url)
    dialect_name = url.get_backend_name()
    if dialect_name not in SUPPORTED_DIALECTS:
        raise UnsupportedDatabaseDialect(
            "RouteDeck SQLAlchemy persistence requires SQLite or PostgreSQL"
        )
    connect_args: dict[str, object] = {}
    if dialect_name == "sqlite":
        _prepare_sqlite_path(url.database)
        connect_args = {
            "check_same_thread": False,
            "timeout": busy_timeout.total_seconds(),
        }
    engine = create_engine(
        url,
        connect_args=connect_args,
        pool_pre_ping=True,
    )
    if dialect_name == "sqlite":
        _configure_sqlite(engine, busy_timeout)
    try:
        migrate_database(engine)
    except BaseException:
        engine.dispose()
        raise
    return DatabaseRuntime(
        engine=engine,
        session_factory=sessionmaker(engine, expire_on_commit=False),
        dialect_name=dialect_name,
        database_url=engine.url.render_as_string(hide_password=True),
    )


def migrate_database(engine: Engine) -> int:
    Base.metadata.create_all(engine)
    with Session(engine) as database, database.begin():
        applied = set(database.scalars(select(SchemaMigrationRow.version)).all())
        future = tuple(
            version for version in applied if version > PERSISTENCE_SCHEMA_VERSION
        )
        if future:
            raise UnsupportedDatabaseSchema(
                f"database schema {max(future)} is newer than supported schema "
                f"{PERSISTENCE_SCHEMA_VERSION}"
            )
        if PERSISTENCE_SCHEMA_VERSION not in applied:
            database.add(
                SchemaMigrationRow(
                    version=PERSISTENCE_SCHEMA_VERSION,
                    applied_at=datetime.now(timezone.utc),
                )
            )
    return PERSISTENCE_SCHEMA_VERSION


def _prepare_sqlite_path(database: str | None) -> None:
    if database in {None, "", ":memory:"}:
        return
    Path(database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


def _configure_sqlite(engine: Engine, busy_timeout: timedelta) -> None:
    timeout_ms = int(busy_timeout.total_seconds() * 1_000)

    @event.listens_for(engine, "connect")
    def configure_connection(dbapi_connection: object, _record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            journal_mode = str(cursor.fetchone()[0]).lower()
            if journal_mode != "wal":
                raise RuntimeError("RouteDeck SQLite requires WAL journal mode")
            cursor.execute("PRAGMA synchronous=FULL")
            cursor.execute(f"PRAGMA busy_timeout={timeout_ms}")
        finally:
            cursor.close()


__all__ = [
    "DatabaseRuntime",
    "PERSISTENCE_SCHEMA_VERSION",
    "UnsupportedDatabaseDialect",
    "UnsupportedDatabaseSchema",
    "migrate_database",
    "open_database",
]
