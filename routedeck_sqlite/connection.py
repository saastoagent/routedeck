from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class SqliteConnectionSettings:
    busy_timeout: timedelta = timedelta(seconds=5)

    def __post_init__(self) -> None:
        if self.busy_timeout <= timedelta(0):
            raise ValueError("busy_timeout must be positive")

    @property
    def busy_timeout_milliseconds(self) -> int:
        return int(self.busy_timeout.total_seconds() * 1_000)


def open_sqlite_connection(
    database_path: str | Path,
    *,
    settings: SqliteConnectionSettings | None = None,
) -> sqlite3.Connection:
    resolved = Path(database_path).expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    effective = settings or SqliteConnectionSettings()
    connection = sqlite3.connect(
        resolved,
        timeout=effective.busy_timeout.total_seconds(),
        isolation_level=None,
        check_same_thread=False,
    )
    connection.row_factory = sqlite3.Row
    try:
        journal_mode = str(connection.execute("PRAGMA journal_mode=WAL").fetchone()[0])
        if journal_mode.lower() != "wal":
            raise RuntimeError("RouteDeck SQLite requires WAL journal mode")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute(f"PRAGMA busy_timeout={effective.busy_timeout_milliseconds}")
        if int(connection.execute("PRAGMA foreign_keys").fetchone()[0]) != 1:
            raise RuntimeError("RouteDeck SQLite requires foreign key enforcement")
        if int(connection.execute("PRAGMA synchronous").fetchone()[0]) != 2:
            raise RuntimeError("RouteDeck SQLite requires synchronous=FULL")
        return connection
    except BaseException:
        connection.close()
        raise


@contextmanager
def immediate_transaction(connection: sqlite3.Connection) -> Iterator[None]:
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        connection.rollback()
        raise
    else:
        connection.commit()


__all__ = [
    "SqliteConnectionSettings",
    "immediate_transaction",
    "open_sqlite_connection",
]
