"""Product-neutral FastAPI and SSE integration for RouteDeck."""

from .dependencies import (
    EventWakeupNotifier,
    GuestCookieSettings,
    InProcessEventNotifier,
    RouteDeckDependencies,
    RouteDeckDependencyUnavailable,
    SensitiveCodec,
    SessionInitializer,
    SessionFactory,
    SessionProjector,
    SseSettings,
)
from .conversation import (
    ChatStreamRequest,
    PublicConversationTurn,
    RouteDeckConversationDependencies,
    create_routedeck_conversation_router,
    public_conversation,
    stream_agent_chat,
)
from .router import (
    DispatchRequest,
    PrivateFormWriteRequest,
    ReviewRequest,
    create_routedeck_router,
    create_routedeck_router_from_provider,
)
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
    "ChatStreamRequest",
    "DispatchRequest",
    "EventWakeupNotifier",
    "GuestCookieSettings",
    "InProcessEventNotifier",
    "PrivateFormWriteRequest",
    "PublicConversationTurn",
    "ReviewRequest",
    "RouteDeckConversationDependencies",
    "RouteDeckDependencies",
    "RouteDeckDependencyUnavailable",
    "RouteDeckMutationPolicy",
    "RouteDeckMutationRejected",
    "SameOriginMutationPolicy",
    "SensitiveCodec",
    "SessionInitializer",
    "SessionFactory",
    "SessionProjector",
    "SseSettings",
    "create_routedeck_router",
    "create_routedeck_conversation_router",
    "create_routedeck_router_from_provider",
    "encode_event",
    "encode_heartbeat",
    "encode_stream_reset",
    "public_conversation",
    "stream_agent_chat",
    "stream_events",
]
