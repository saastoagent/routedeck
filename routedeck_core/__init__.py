from .authoring import (
    RouteDeckManifestBuilder as RouteDeckManifestBuilder,
    route_deck_action as route_deck_action,
    route_deck_edge as route_deck_edge,
    route_deck_field as route_deck_field,
    route_deck_node as route_deck_node,
)
from .app import (
    ApplicationSpec,
    CompiledRouteDeckApp,
    FeatureSpec,
    RouteDeckApp as RouteDeckApp,
    bind_app,
    compile_app,
)
from .dispatch import RouteDeckActionDispatcher, RouteDeckActionResult
from .errors import FailureKind, FailureSafeDetails, RouteDeckFailure
from .models import (
    RouteDeckActionCard,
    RouteDeckActionSpec,
    RouteDeckActionField,
    RouteDeckAvailableEntity,
    RouteDeckBindingExpression,
    RouteDeckCapabilitySpec,
    RouteDeckContextLens,
    RouteDeckDeepLink,
    RouteDeckDispatchInput,
    RouteDeckDispatchResult,
    RouteDeckEdgeSpec,
    RouteDeckEntityOperationBinding,
    RouteDeckEvent,
    RouteDeckFieldSpec,
    RouteDeckGraphManifest,
    RouteDeckGraphManifestAction,
    RouteDeckGraphManifestEdge,
    RouteDeckGraphManifestNode,
    RouteDeckGraphMessage,
    RouteDeckGraphNavigationLocation,
    RouteDeckGraphRequest,
    RouteDeckGraphResponse,
    RouteDeckGraphState,
    RouteDeckIntrospection,
    RouteDeckManifest as RouteDeckManifest,
    RouteDeckLocation,
    RouteDeckNavGraph,
    RouteDeckNavGraphEdge,
    RouteDeckNavGraphNode,
    RouteDeckNavigationState,
    RouteDeckNodeSpec,
    RouteDeckOperation,
    RouteDeckProjection,
    RouteDeckRuntimeState,
    RouteDeckRuntimeSnapshot,
    RouteDeckSensitivePolicy,
    RouteDeckSemanticObservation,
    RouteDeckSurface,
    RouteDeckSurfaceAffordance,
    RouteDeckSurfaceInteractionEvent,
    RouteDeckUIArtifact,
)
from .operations import (
    RouteDeckOperationPolicy,
    RouteDeckOperationRequestPolicy,
    RouteDeckRouteActionIds,
)
from .projector import RouteDeckStateProjector
from .navigation import (
    ROUTEDECK_PENDING_OPERATION_ARGS_PARAM,
    ROUTEDECK_PENDING_OPERATION_ID_PARAM,
    RouteDeckGraphNavigationController,
    RouteDeckNavigationPolicy,
    RouteDeckNavigationTransition,
)
from .context import ContextScopeBuilder, OperationContextScope
from .contracts.events import CanonicalRouteDeckEvent
from .contracts.effects import SessionEffects
from .contracts.projection import PublicProjection
from .contracts.retention import RouteDeckRetentionPolicy
from .contracts.session import RouteDeckSession, SessionSnapshot
from .navigation.deep_links import DeepLinkEngine
from .navigation.engine import NavigationEngine
from .ports import RouteDeckNotifier, RouteDeckSessionStore
from .projection import ProjectionProjector
from .supervision import RouteDeckOperationRunner
from .handles import new_opaque_handle
from .runtime import (
    RouteDeckRuntime,
    build_dispatch_result_completed_event,
    build_dispatch_result,
    build_dispatch_state_event,
    build_operation_completed_event,
    build_projection,
    build_projection_update_event,
    build_runtime_snapshot,
    build_runtime_state,
    reachable_nodes,
)
from .surfaces import RouteDeckSurfaceRegistry
from .validation import (
    RouteDeckValidationError,
    validate_manifest as validate_manifest,
)


def __getattr__(name: str) -> object:
    """Resolve the legacy runtime subclass without publishing it in ``__all__``."""

    if name == "RouteDeckRuntimeBase":
        from .runtime import RouteDeckRuntimeBase

        return RouteDeckRuntimeBase
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ApplicationSpec",
    "CanonicalRouteDeckEvent",
    "CompiledRouteDeckApp",
    "ContextScopeBuilder",
    "DeepLinkEngine",
    "FailureKind",
    "FailureSafeDetails",
    "FeatureSpec",
    "NavigationEngine",
    "OperationContextScope",
    "ProjectionProjector",
    "PublicProjection",
    "RouteDeckActionDispatcher",
    "RouteDeckActionResult",
    "RouteDeckActionCard",
    "RouteDeckActionField",
    "RouteDeckActionSpec",
    "RouteDeckAvailableEntity",
    "RouteDeckBindingExpression",
    "RouteDeckCapabilitySpec",
    "RouteDeckContextLens",
    "RouteDeckDeepLink",
    "RouteDeckDispatchInput",
    "RouteDeckDispatchResult",
    "RouteDeckEdgeSpec",
    "RouteDeckEntityOperationBinding",
    "RouteDeckEvent",
    "RouteDeckFieldSpec",
    "RouteDeckGraphManifest",
    "RouteDeckGraphManifestAction",
    "RouteDeckGraphManifestEdge",
    "RouteDeckGraphManifestNode",
    "RouteDeckGraphMessage",
    "RouteDeckGraphNavigationLocation",
    "RouteDeckGraphRequest",
    "RouteDeckGraphResponse",
    "RouteDeckGraphState",
    "RouteDeckGraphNavigationController",
    "RouteDeckIntrospection",
    "RouteDeckNavigationPolicy",
    "RouteDeckLocation",
    "RouteDeckNavigationTransition",
    "RouteDeckNavGraph",
    "RouteDeckNavGraphEdge",
    "RouteDeckNavGraphNode",
    "RouteDeckNavigationState",
    "RouteDeckNodeSpec",
    "RouteDeckOperation",
    "RouteDeckOperationPolicy",
    "RouteDeckOperationRunner",
    "RouteDeckOperationRequestPolicy",
    "RouteDeckProjection",
    "RouteDeckRetentionPolicy",
    "RouteDeckRouteActionIds",
    "RouteDeckStateProjector",
    "RouteDeckRuntime",
    "RouteDeckFailure",
    "RouteDeckRuntimeState",
    "RouteDeckRuntimeSnapshot",
    "RouteDeckSession",
    "RouteDeckSessionStore",
    "RouteDeckNotifier",
    "RouteDeckSensitivePolicy",
    "RouteDeckSemanticObservation",
    "RouteDeckSurface",
    "RouteDeckSurfaceAffordance",
    "RouteDeckSurfaceInteractionEvent",
    "RouteDeckSurfaceRegistry",
    "RouteDeckUIArtifact",
    "SessionSnapshot",
    "SessionEffects",
    "RouteDeckValidationError",
    "ROUTEDECK_PENDING_OPERATION_ARGS_PARAM",
    "ROUTEDECK_PENDING_OPERATION_ID_PARAM",
    "build_dispatch_result_completed_event",
    "build_dispatch_result",
    "build_dispatch_state_event",
    "build_operation_completed_event",
    "build_projection",
    "build_projection_update_event",
    "build_runtime_snapshot",
    "build_runtime_state",
    "bind_app",
    "compile_app",
    "reachable_nodes",
    "new_opaque_handle",
]
