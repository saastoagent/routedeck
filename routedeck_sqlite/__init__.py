"""Fenced SQLite persistence integration for RouteDeck."""

from .codec import (
    FernetSensitiveCodec,
    InvalidEncryptionKey,
    MissingEncryptionKey,
    SensitiveCodec,
    SensitiveDataIntegrityError,
)
from .connection import SqliteConnectionSettings
from .instance_lease import (
    RouteDeckInstanceAlreadyRunning,
    RouteDeckInstanceLeaseLost,
    RouteDeckWorkerConfigurationError,
)
from .migrations import UnsupportedDatabaseSchema
from .store import SqliteSessionStore, UtcClock

__all__ = [
    "FernetSensitiveCodec",
    "InvalidEncryptionKey",
    "MissingEncryptionKey",
    "RouteDeckInstanceAlreadyRunning",
    "RouteDeckInstanceLeaseLost",
    "RouteDeckWorkerConfigurationError",
    "SensitiveCodec",
    "SensitiveDataIntegrityError",
    "SqliteConnectionSettings",
    "SqliteSessionStore",
    "UnsupportedDatabaseSchema",
    "UtcClock",
]
