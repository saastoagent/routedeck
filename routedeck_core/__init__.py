"""Canonical public API for the compiled RouteDeck interaction framework."""

from __future__ import annotations

from .app import (
    Application,
    BoundApplication,
    CompiledApplication,
    FeatureBindings,
    Feature,
    bind_app,
    compile_app,
)
from .contracts.effects import SessionEffects
from .contracts.events import RouteDeckEvent, RouteDeckEventType
from .contracts.failures import FailureKind, FailureSafeDetails, RouteDeckFailure
from .contracts.projection import PublicProjection
from .contracts.retention import RouteDeckRetentionPolicy
from .contracts.session import RouteDeckSession, SessionSnapshot
from .context import ContextScopeBuilder, OperationContextScope
from .handles import new_opaque_handle
from .navigation.deep_links import DeepLinkEngine
from .navigation.engine import NavigationEngine
from .ports import RouteDeckNotifier, RouteDeckSessionStore, SensitiveCodec
from .projection import ConfiguredSessionProjector, ProjectionProjector
from .runtime import (
    RouteDeckRuntime,
    RouteDeckRuntimeLifecycle,
    RouteDeckRuntimeServices,
    build_routedeck_runtime,
)
from .state import RouteDeckSessionAggregate
from .supervision import RouteDeckOperationRunner

__all__ = [
    "Application",
    "BoundApplication",
    "CompiledApplication",
    "ConfiguredSessionProjector",
    "ContextScopeBuilder",
    "DeepLinkEngine",
    "FailureKind",
    "FailureSafeDetails",
    "FeatureBindings",
    "Feature",
    "NavigationEngine",
    "OperationContextScope",
    "ProjectionProjector",
    "PublicProjection",
    "RouteDeckEventType",
    "RouteDeckEvent",
    "RouteDeckFailure",
    "RouteDeckNotifier",
    "RouteDeckOperationRunner",
    "RouteDeckRuntime",
    "RouteDeckRuntimeLifecycle",
    "RouteDeckRuntimeServices",
    "RouteDeckRetentionPolicy",
    "RouteDeckSession",
    "RouteDeckSessionAggregate",
    "RouteDeckSessionStore",
    "SensitiveCodec",
    "SessionEffects",
    "SessionSnapshot",
    "bind_app",
    "compile_app",
    "build_routedeck_runtime",
    "new_opaque_handle",
]
