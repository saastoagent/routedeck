"""Portable SQLAlchemy persistence for RouteDeck."""

from .codec import (
    FernetSensitiveCodec,
    InvalidEncryptionKey,
    MissingEncryptionKey,
    SensitiveDataIntegrityError,
)
from .application_runtime import (
    ApplicationFactory,
    SqlAlchemyRuntimeResources,
    open_sqlalchemy_routedeck_runtime,
)
from .database import (
    PERSISTENCE_SCHEMA_VERSION,
    UnsupportedDatabaseDialect,
    UnsupportedDatabaseSchema,
)
from .lease import (
    RouteDeckInstanceAlreadyRunning,
    RouteDeckInstanceLeaseLost,
    RouteDeckWorkerConfigurationError,
)
from .store import SqlAlchemySessionStore

__all__ = [
    "ApplicationFactory",
    "FernetSensitiveCodec",
    "InvalidEncryptionKey",
    "MissingEncryptionKey",
    "PERSISTENCE_SCHEMA_VERSION",
    "RouteDeckInstanceAlreadyRunning",
    "RouteDeckInstanceLeaseLost",
    "RouteDeckWorkerConfigurationError",
    "SensitiveDataIntegrityError",
    "SqlAlchemyRuntimeResources",
    "SqlAlchemySessionStore",
    "UnsupportedDatabaseDialect",
    "UnsupportedDatabaseSchema",
    "open_sqlalchemy_routedeck_runtime",
]
