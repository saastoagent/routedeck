from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from .connection import immediate_transaction
from .schema import (
    CREATE_MIGRATION_TABLE,
    SCHEMA_V1_STATEMENTS,
    SCHEMA_V2_STATEMENTS,
    SCHEMA_VERSION,
)


class UnsupportedDatabaseSchema(RuntimeError):
    pass


def migrate(connection: sqlite3.Connection) -> int:
    """Apply every declared migration atomically and fail on any DDL error."""

    with immediate_transaction(connection):
        connection.execute(CREATE_MIGRATION_TABLE)
        applied = {
            int(row["version"])
            for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()
        }
        future = tuple(version for version in applied if version > SCHEMA_VERSION)
        if future:
            raise UnsupportedDatabaseSchema(
                f"database schema {max(future)} is newer than supported schema {SCHEMA_VERSION}"
            )
        if 1 not in applied:
            for statement in SCHEMA_V1_STATEMENTS:
                connection.execute(statement)
            connection.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (1, datetime.now(timezone.utc).isoformat()),
            )
            applied.add(1)
        if 2 not in applied:
            for statement in SCHEMA_V2_STATEMENTS:
                connection.execute(statement)
            connection.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (2, datetime.now(timezone.utc).isoformat()),
            )
    return SCHEMA_VERSION


__all__ = ["UnsupportedDatabaseSchema", "migrate"]
