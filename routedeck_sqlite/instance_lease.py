from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta

from .connection import immediate_transaction


class RouteDeckInstanceAlreadyRunning(RuntimeError):
    pass


class RouteDeckInstanceLeaseLost(RuntimeError):
    pass


class RouteDeckWorkerConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class ApplicationLease:
    instance_id: str
    fencing_token: int
    expires_at: datetime


def acquire_application_lease(
    connection: sqlite3.Connection,
    *,
    instance_id: str,
    now: datetime,
    ttl: timedelta,
) -> ApplicationLease:
    _validate(instance_id=instance_id, now=now, ttl=ttl)
    with immediate_transaction(connection):
        row = connection.execute(
            "SELECT instance_id, fencing_token, expires_at, released_at "
            "FROM application_lease WHERE slot = 1"
        ).fetchone()
        if row is not None:
            expires_at = datetime.fromisoformat(str(row["expires_at"]))
            if row["released_at"] is None and expires_at > now:
                raise RouteDeckInstanceAlreadyRunning(
                    "another RouteDeck application instance owns this database"
                )
            fencing_token = int(row["fencing_token"]) + 1
        else:
            fencing_token = 1
        expires_at = now + ttl
        connection.execute(
            """
            INSERT INTO application_lease(
                slot, instance_id, fencing_token, heartbeat_at, expires_at, released_at
            ) VALUES (1, ?, ?, ?, ?, NULL)
            ON CONFLICT(slot) DO UPDATE SET
                instance_id = excluded.instance_id,
                fencing_token = excluded.fencing_token,
                heartbeat_at = excluded.heartbeat_at,
                expires_at = excluded.expires_at,
                released_at = NULL
            """,
            (instance_id, fencing_token, now.isoformat(), expires_at.isoformat()),
        )
    return ApplicationLease(instance_id, fencing_token, expires_at)


def assert_application_lease(
    connection: sqlite3.Connection,
    lease: ApplicationLease,
    *,
    now: datetime,
) -> None:
    row = connection.execute(
        "SELECT instance_id, fencing_token, expires_at, released_at "
        "FROM application_lease WHERE slot = 1"
    ).fetchone()
    if (
        row is None
        or str(row["instance_id"]) != lease.instance_id
        or int(row["fencing_token"]) != lease.fencing_token
        or row["released_at"] is not None
        or datetime.fromisoformat(str(row["expires_at"])) <= now
    ):
        raise RouteDeckInstanceLeaseLost(
            "RouteDeck application lease is no longer valid"
        )


def heartbeat_application_lease(
    connection: sqlite3.Connection,
    lease: ApplicationLease,
    *,
    now: datetime,
    ttl: timedelta,
) -> ApplicationLease:
    _validate(instance_id=lease.instance_id, now=now, ttl=ttl)
    expires_at = now + ttl
    with immediate_transaction(connection):
        assert_application_lease(connection, lease, now=now)
        changed = connection.execute(
            """
            UPDATE application_lease
            SET heartbeat_at = ?, expires_at = ?
            WHERE slot = 1 AND instance_id = ? AND fencing_token = ?
              AND released_at IS NULL
            """,
            (
                now.isoformat(),
                expires_at.isoformat(),
                lease.instance_id,
                lease.fencing_token,
            ),
        ).rowcount
        if changed != 1:
            raise RouteDeckInstanceLeaseLost(
                "RouteDeck application lease heartbeat was fenced"
            )
    return ApplicationLease(lease.instance_id, lease.fencing_token, expires_at)


def release_application_lease(
    connection: sqlite3.Connection,
    lease: ApplicationLease,
    *,
    now: datetime,
) -> None:
    with immediate_transaction(connection):
        assert_application_lease(connection, lease, now=now)
        changed = connection.execute(
            """
            UPDATE application_lease
            SET heartbeat_at = ?, expires_at = ?, released_at = ?
            WHERE slot = 1 AND instance_id = ? AND fencing_token = ?
              AND released_at IS NULL
            """,
            (
                now.isoformat(),
                now.isoformat(),
                now.isoformat(),
                lease.instance_id,
                lease.fencing_token,
            ),
        ).rowcount
        if changed != 1:
            raise RouteDeckInstanceLeaseLost(
                "RouteDeck application lease release was fenced"
            )


def _validate(*, instance_id: str, now: datetime, ttl: timedelta) -> None:
    if not instance_id:
        raise ValueError("instance_id is required")
    if now.tzinfo is None:
        raise ValueError("instance lease timestamps must be timezone-aware")
    if ttl <= timedelta(0):
        raise ValueError("application lease TTL must be positive")


__all__ = [
    "ApplicationLease",
    "RouteDeckInstanceAlreadyRunning",
    "RouteDeckInstanceLeaseLost",
    "RouteDeckWorkerConfigurationError",
    "acquire_application_lease",
    "assert_application_lease",
    "heartbeat_application_lease",
    "release_application_lease",
]
