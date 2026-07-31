"""Product-neutral FastAPI and SSE integration for RouteDeck."""

from .dependencies import (
    EventWakeupNotifier,
    GuestCookieSettings,
    RouteDeckDependencies,
    RouteDeckDependencyUnavailable,
    RouteDeckSessionSelector,
    SessionProvisioner,
    SessionProjector,
    SseSettings,
)
from .session_http import GuestCookieSessionSelector
from .runtime import RuntimeProvider, dependencies_from_runtime
from .conversation_projection import PublicConversationTurn, public_conversation
from .conversation_replay import conversation_fingerprint
from .conversation_stream import ConversationTurnRequest, stream_agent_turn
from .conversation_runs import (
    ConversationRunCoordinator,
    ConversationRunFailure,
    ConversationRunSnapshot,
    ConversationRunStage,
    ensure_current_node_entry_turn,
    entry_turn_request_id,
)
from .contracts import (
    AssistantTurnRequest,
    ChatStreamRequest,
    ConversationRunStartRequest,
    DispatchRequest,
    PrivateFormWriteRequest,
    ReviewRequest,
)
from .router import create_routedeck_router_from_runtime_provider
from .sse import (
    encode_event,
    encode_heartbeat,
    encode_stream_reset,
    stream_events,
)
from .security import (
    RouteDeckMutationPolicy,
    RouteDeckMutationRejected,
    SameOriginMutationPolicy,
)

__all__ = [
    "AssistantTurnRequest",
    "ChatStreamRequest",
    "ConversationTurnRequest",
    "ConversationRunStartRequest",
    "ConversationRunCoordinator",
    "ConversationRunFailure",
    "ConversationRunSnapshot",
    "ConversationRunStage",
    "DispatchRequest",
    "EventWakeupNotifier",
    "GuestCookieSettings",
    "GuestCookieSessionSelector",
    "PrivateFormWriteRequest",
    "PublicConversationTurn",
    "ReviewRequest",
    "RouteDeckDependencies",
    "RouteDeckDependencyUnavailable",
    "RouteDeckMutationPolicy",
    "RouteDeckMutationRejected",
    "RouteDeckSessionSelector",
    "RuntimeProvider",
    "SameOriginMutationPolicy",
    "SessionProvisioner",
    "SessionProjector",
    "SseSettings",
    "conversation_fingerprint",
    "create_routedeck_router_from_runtime_provider",
    "dependencies_from_runtime",
    "ensure_current_node_entry_turn",
    "entry_turn_request_id",
    "encode_event",
    "encode_heartbeat",
    "encode_stream_reset",
    "public_conversation",
    "stream_agent_turn",
    "stream_events",
]
