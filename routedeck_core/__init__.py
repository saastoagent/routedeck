from .authoring import (
    RouteDeckManifestBuilder,
    route_deck_action,
    route_deck_edge,
    route_deck_field,
    route_deck_node,
)
from .app import RouteDeckApp
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
    RouteDeckManifest,
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
from .contracts.projection import PublicProjection
from .contracts.session import RouteDeckSession, SessionSnapshot
from .navigation.deep_links import DeepLinkEngine
from .navigation.engine import NavigationEngine
from .ports import RouteDeckNotifier, RouteDeckSessionStore
from .projection import ProjectionProjector
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
from .validation import RouteDeckValidationError, validate_manifest


def __getattr__(name: str) -> object:
    """Resolve the legacy runtime subclass without publishing it in ``__all__``."""

    if name == "RouteDeckRuntimeBase":
        from .runtime import RouteDeckRuntimeBase

        return RouteDeckRuntimeBase
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "CanonicalRouteDeckEvent",
    "ContextScopeBuilder",
    "DeepLinkEngine",
    "FailureKind",
    "FailureSafeDetails",
    "NavigationEngine",
    "OperationContextScope",
    "ProjectionProjector",
    "PublicProjection",
    "RouteDeckActionDispatcher",
    "RouteDeckApp",
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
    "RouteDeckManifest",
    "RouteDeckManifestBuilder",
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
    "RouteDeckOperationRequestPolicy",
    "RouteDeckProjection",
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
    "reachable_nodes",
    "route_deck_action",
    "route_deck_edge",
    "route_deck_field",
    "route_deck_node",
    "validate_manifest",
]
