from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from cryptography.fernet import Fernet

from routedeck_sqlite import (
    FernetSensitiveCodec,
    InvalidEncryptionKey,
    MissingEncryptionKey,
    RouteDeckInstanceAlreadyRunning,
    RouteDeckInstanceLeaseLost,
    SensitiveDataIntegrityError,
    SqliteConnectionSettings,
    UnsupportedDatabaseSchema,
)
from routedeck_sqlite.connection import immediate_transaction, open_sqlite_connection
from routedeck_sqlite.instance_lease import (
    acquire_application_lease,
    assert_application_lease,
    heartbeat_application_lease,
    release_application_lease,
)
from routedeck_sqlite.migrations import migrate
from routedeck_sqlite.schema import CREATE_MIGRATION_TABLE, SCHEMA_VERSION


def test_sensitive_codec_rejects_missing_invalid_and_non_bytes_values() -> None:
    with pytest.raises(MissingEncryptionKey):
        FernetSensitiveCodec("")
    with pytest.raises(InvalidEncryptionKey):
        FernetSensitiveCodec("not-a-fernet-key")

    codec = FernetSensitiveCodec(Fernet.generate_key())
    with pytest.raises(TypeError, match="sensitive values must be bytes"):
        codec.encrypt("private")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="encrypted values must be bytes"):
        codec.decrypt("ciphertext")  # type: ignore[arg-type]


def test_sensitive_codec_fails_closed_when_ciphertext_is_tampered() -> None:
    codec = FernetSensitiveCodec(Fernet.generate_key())
    ciphertext = bytearray(codec.encrypt(b"private buyer state"))
    ciphertext[-1] ^= 1

    with pytest.raises(SensitiveDataIntegrityError):
        codec.decrypt(bytes(ciphertext))


def test_connection_settings_and_transaction_failure_semantics() -> None:
    with pytest.raises(ValueError, match="busy_timeout must be positive"):
        SqliteConnectionSettings(busy_timeout=timedelta(0))

    connection = sqlite3.connect(":memory:", isolation_level=None)
    connection.execute("CREATE TABLE values_table(value TEXT NOT NULL)")
    with immediate_transaction(connection):
        connection.execute("INSERT INTO values_table(value) VALUES ('committed')")

    with pytest.raises(RuntimeError, match="abort transaction"):
        with immediate_transaction(connection):
            connection.execute("INSERT INTO values_table(value) VALUES ('rolled-back')")
            raise RuntimeError("abort transaction")

    assert connection.execute("SELECT value FROM values_table").fetchall() == [
        ("committed",)
    ]
    connection.close()


class _PragmaResult:
    def __init__(self, value: object) -> None:
        self._value = value

    def fetchone(self) -> tuple[object]:
        return (self._value,)


class _PragmaConnection:
    def __init__(
        self,
        *,
        journal_mode: str = "wal",
        foreign_keys: int = 1,
        synchronous: int = 2,
    ) -> None:
        self.journal_mode = journal_mode
        self.foreign_keys = foreign_keys
        self.synchronous = synchronous
        self.closed = False
        self.row_factory: object | None = None

    def execute(self, sql: str) -> _PragmaResult:
        if sql == "PRAGMA journal_mode=WAL":
            return _PragmaResult(self.journal_mode)
        if sql == "PRAGMA foreign_keys":
            return _PragmaResult(self.foreign_keys)
        if sql == "PRAGMA synchronous":
            return _PragmaResult(self.synchronous)
        return _PragmaResult(None)

    def close(self) -> None:
        self.closed = True


@pytest.mark.parametrize(
    ("connection", "message"),
    [
        (_PragmaConnection(journal_mode="delete"), "WAL journal mode"),
        (_PragmaConnection(foreign_keys=0), "foreign key enforcement"),
        (_PragmaConnection(synchronous=1), "synchronous=FULL"),
    ],
)
def test_connection_open_fails_closed_when_required_pragmas_are_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    connection: _PragmaConnection,
    message: str,
) -> None:
    monkeypatch.setattr(sqlite3, "connect", lambda *args, **kwargs: connection)

    with pytest.raises(RuntimeError, match=message):
        open_sqlite_connection(tmp_path / "unusable.sqlite")

    assert connection.closed is True


def _lease_database(tmp_path: Path, name: str) -> sqlite3.Connection:
    connection = open_sqlite_connection(tmp_path / name)
    migrate(connection)
    return connection


def test_application_lease_lifecycle_fences_competing_and_released_owners(
    tmp_path: Path,
) -> None:
    connection = _lease_database(tmp_path, "lease-lifecycle.sqlite")
    started_at = datetime(2026, 7, 12, tzinfo=timezone.utc)
    ttl = timedelta(seconds=30)
    first = acquire_application_lease(
        connection,
        instance_id="first",
        now=started_at,
        ttl=ttl,
    )

    with pytest.raises(RouteDeckInstanceAlreadyRunning):
        acquire_application_lease(
            connection,
            instance_id="competitor",
            now=started_at + timedelta(seconds=1),
            ttl=ttl,
        )

    heartbeat = heartbeat_application_lease(
        connection,
        first,
        now=started_at + timedelta(seconds=2),
        ttl=ttl,
    )
    assert heartbeat.expires_at == started_at + timedelta(seconds=32)
    assert_application_lease(
        connection,
        heartbeat,
        now=started_at + timedelta(seconds=3),
    )
    release_application_lease(
        connection,
        heartbeat,
        now=started_at + timedelta(seconds=4),
    )
    with pytest.raises(RouteDeckInstanceLeaseLost):
        assert_application_lease(
            connection,
            heartbeat,
            now=started_at + timedelta(seconds=4),
        )

    replacement = acquire_application_lease(
        connection,
        instance_id="replacement",
        now=started_at + timedelta(seconds=5),
        ttl=ttl,
    )
    assert replacement.fencing_token == first.fencing_token + 1
    connection.close()


def test_application_lease_rejects_invalid_inputs_and_expiry(tmp_path: Path) -> None:
    connection = _lease_database(tmp_path, "lease-validation.sqlite")
    aware = datetime(2026, 7, 12, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="instance_id is required"):
        acquire_application_lease(
            connection,
            instance_id="",
            now=aware,
            ttl=timedelta(seconds=5),
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        acquire_application_lease(
            connection,
            instance_id="naive",
            now=aware.replace(tzinfo=None),
            ttl=timedelta(seconds=5),
        )
    with pytest.raises(ValueError, match="TTL must be positive"):
        acquire_application_lease(
            connection,
            instance_id="zero-ttl",
            now=aware,
            ttl=timedelta(0),
        )

    lease = acquire_application_lease(
        connection,
        instance_id="expires",
        now=aware,
        ttl=timedelta(seconds=5),
    )
    with pytest.raises(RouteDeckInstanceLeaseLost):
        assert_application_lease(
            connection,
            lease,
            now=aware + timedelta(seconds=5),
        )
    connection.close()


@pytest.mark.parametrize("operation", ["heartbeat", "release"])
def test_application_lease_update_detects_a_concurrent_fence(
    tmp_path: Path,
    operation: str,
) -> None:
    connection = _lease_database(tmp_path, f"lease-fence-{operation}.sqlite")
    now = datetime(2026, 7, 12, tzinfo=timezone.utc)
    lease = acquire_application_lease(
        connection,
        instance_id="owner",
        now=now,
        ttl=timedelta(seconds=30),
    )
    connection.execute(
        """
        CREATE TRIGGER fence_application_lease_update
        BEFORE UPDATE ON application_lease
        BEGIN
            SELECT RAISE(IGNORE);
        END
        """
    )

    with pytest.raises(RouteDeckInstanceLeaseLost, match="fenced"):
        if operation == "heartbeat":
            heartbeat_application_lease(
                connection,
                lease,
                now=now + timedelta(seconds=1),
                ttl=timedelta(seconds=30),
            )
        else:
            release_application_lease(
                connection,
                lease,
                now=now + timedelta(seconds=1),
            )
    connection.close()


def test_migration_rejects_a_database_from_a_newer_schema(tmp_path: Path) -> None:
    connection = open_sqlite_connection(tmp_path / "future-schema.sqlite")
    connection.execute(CREATE_MIGRATION_TABLE)
    connection.execute(
        "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
        (SCHEMA_VERSION + 1, datetime.now(timezone.utc).isoformat()),
    )

    with pytest.raises(UnsupportedDatabaseSchema, match="newer than supported"):
        migrate(connection)
    rows = connection.execute("SELECT version FROM schema_migrations").fetchall()
    assert [int(row["version"]) for row in rows] == [SCHEMA_VERSION + 1]
    connection.close()
