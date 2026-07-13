from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ApplicationLeaseRow


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
    database: Session,
    *,
    instance_id: str,
    now: datetime,
    ttl: timedelta,
) -> ApplicationLease:
    _validate(instance_id=instance_id, now=now, ttl=ttl)
    row = database.scalar(
        select(ApplicationLeaseRow)
        .where(ApplicationLeaseRow.slot == 1)
        .with_for_update()
    )
    if row is not None and row.released_at is None and row.expires_at > now:
        raise RouteDeckInstanceAlreadyRunning(
            "another RouteDeck application instance owns this database"
        )
    fencing_token = (row.fencing_token if row is not None else 0) + 1
    expires_at = now + ttl
    if row is None:
        row = ApplicationLeaseRow(
            slot=1,
            instance_id=instance_id,
            fencing_token=fencing_token,
            heartbeat_at=now,
            expires_at=expires_at,
            released_at=None,
        )
        database.add(row)
    else:
        row.instance_id = instance_id
        row.fencing_token = fencing_token
        row.heartbeat_at = now
        row.expires_at = expires_at
        row.released_at = None
    database.flush()
    return ApplicationLease(instance_id, fencing_token, expires_at)


def assert_application_lease(
    database: Session,
    lease: ApplicationLease,
    *,
    now: datetime,
) -> ApplicationLeaseRow:
    row = database.get(ApplicationLeaseRow, 1)
    if (
        row is None
        or row.instance_id != lease.instance_id
        or row.fencing_token != lease.fencing_token
        or row.released_at is not None
        or row.expires_at <= now
    ):
        raise RouteDeckInstanceLeaseLost(
            "RouteDeck application lease is no longer valid"
        )
    return row


def heartbeat_application_lease(
    database: Session,
    lease: ApplicationLease,
    *,
    now: datetime,
    ttl: timedelta,
) -> ApplicationLease:
    _validate(instance_id=lease.instance_id, now=now, ttl=ttl)
    row = assert_application_lease(database, lease, now=now)
    expires_at = now + ttl
    row.heartbeat_at = now
    row.expires_at = expires_at
    database.flush()
    return ApplicationLease(lease.instance_id, lease.fencing_token, expires_at)


def release_application_lease(
    database: Session,
    lease: ApplicationLease,
    *,
    now: datetime,
) -> None:
    row = assert_application_lease(database, lease, now=now)
    row.heartbeat_at = now
    row.expires_at = now
    row.released_at = now
    database.flush()


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
