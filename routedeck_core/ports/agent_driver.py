from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol, TypeAlias, runtime_checkable

from ..contracts.conversation import FinalizedConversationTurn
from ..state.leases import TurnLease

if TYPE_CHECKING:
    from ..contracts.session import SessionSnapshot
    from ..runtime import RouteDeckRuntimeServices


class RouteDeckAgentStreamError(RuntimeError):
    """A product agent violated the RouteDeck conversation-driver contract."""

    def __init__(self, code: str, public_message: str) -> None:
        super().__init__(code)
        self.code = code
        self.public_message = public_message


@dataclass(frozen=True)
class UserMessageTrigger:
    message: str
    user_turn: FinalizedConversationTurn


@dataclass(frozen=True)
class AssistantInitiatedTrigger:
    pass


RouteDeckConversationTrigger: TypeAlias = (
    UserMessageTrigger | AssistantInitiatedTrigger
)


@dataclass(frozen=True)
class RouteDeckAgentTurn:
    session_id: str
    request_id: str
    lease: TurnLease
    trigger: RouteDeckConversationTrigger


@dataclass(frozen=True)
class AssistantTextDelta:
    content: str


@dataclass(frozen=True)
class AssistantTextReset:
    pass


@dataclass(frozen=True)
class AgentReviewRequired:
    operation_id: str
    review_id: str
    expires_at: datetime


@dataclass(frozen=True)
class AgentTurnCompleted:
    turns: tuple[FinalizedConversationTurn, ...]
    assistant_turn_id: str

    def __init__(
        self,
        *,
        turns: Sequence[FinalizedConversationTurn],
        assistant_turn_id: str,
    ) -> None:
        object.__setattr__(self, "turns", tuple(turns))
        object.__setattr__(self, "assistant_turn_id", assistant_turn_id)


RouteDeckAgentEvent: TypeAlias = (
    AssistantTextDelta
    | AssistantTextReset
    | AgentReviewRequired
    | AgentTurnCompleted
)


@runtime_checkable
class RouteDeckAgentDriver(Protocol):
    """Product adapter consumed by RouteDeck's conversation runtime."""

    def stream(
        self,
        turn: RouteDeckAgentTurn,
    ) -> AsyncIterator[RouteDeckAgentEvent]: ...


@runtime_checkable
class RouteDeckAgentContextInspector(Protocol):
    """Optional driver-owned view of the exact context prepared for its model."""

    def inspect_agent_context(
        self,
        snapshot: "SessionSnapshot",
    ) -> dict[str, Any] | None: ...


@runtime_checkable
class RouteDeckAgentDriverFactory(Protocol):
    """Create an optional conversation driver after runtime services exist."""

    def create(
        self,
        services: "RouteDeckRuntimeServices",
    ) -> RouteDeckAgentDriver | None: ...


__all__ = [
    "AgentReviewRequired",
    "AgentTurnCompleted",
    "AssistantInitiatedTrigger",
    "AssistantTextDelta",
    "AssistantTextReset",
    "RouteDeckAgentDriver",
    "RouteDeckAgentContextInspector",
    "RouteDeckAgentDriverFactory",
    "RouteDeckAgentEvent",
    "RouteDeckAgentStreamError",
    "RouteDeckAgentTurn",
    "RouteDeckConversationTrigger",
    "UserMessageTrigger",
]
