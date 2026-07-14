from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from langchain_core.messages import AIMessage

from routedeck_core.contracts.conversation import (
    ConversationRole,
    ConversationTurnStatus,
    FinalizedConversationTurn,
)
from routedeck_core.contracts.failures import FailureKind, RouteDeckFailure
from routedeck_core.contracts.session import SessionSnapshot
from routedeck_core.ports import (
    RouteDeckSessionStore,
    SessionStoreError,
    SessionStoreErrorCode,
)
from routedeck_core.state.leases import TurnClaim, TurnOwnerKind
from routedeck_core.supervision import RouteDeckOperationRunner
from routedeck_core.supervision.outcomes import canonical_json_fingerprint

from .features.catalog import BUYER_HOME_NODE


class BuyerEntryAgent(Protocol):
    async def ainvoke(
        self,
        input: Mapping[str, Any],
        config: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> object: ...


class EntryConversationError(RuntimeError):
    """Raised when the home-entry agent violates its narrow conversation contract."""


async def start_home_conversation(
    *,
    runner: RouteDeckOperationRunner,
    store: RouteDeckSessionStore,
    agent: BuyerEntryAgent,
    session_id: str,
    request_id: str,
    expected_session_version: int,
) -> SessionSnapshot:
    """Persist the first model-authored greeting for an empty buyer.home session."""

    snapshot = await store.load(session_id)
    if (
        snapshot.state.current.node_id != BUYER_HOME_NODE.id
        or any(
            turn.status is ConversationTurnStatus.FINALIZED
            for turn in snapshot.state.conversation
        )
    ):
        return snapshot
    if snapshot.session_version != expected_session_version:
        raise SessionStoreError(SessionStoreErrorCode.VERSION_CONFLICT)

    turn = await runner.begin_turn(
        TurnClaim(
            session_id=session_id,
            expected_session_version=expected_session_version,
            request_id=request_id,
            request_fingerprint=canonical_json_fingerprint(
                "medusa.entry.v1", {"session_id": session_id}
            ),
            owner_kind=TurnOwnerKind.CHAT,
        )
    )
    try:
        result = await agent.ainvoke({"messages": []})
        assistant = _entry_assistant_message(result)
        return await runner.complete_turn(
            turn,
            expected_session_version=expected_session_version,
            turns=(
                FinalizedConversationTurn(
                    turn_id=(
                        assistant.id
                        if isinstance(assistant.id, str) and assistant.id
                        else runner.id_factory("turn")
                    ),
                    role=ConversationRole.ASSISTANT,
                    content=assistant.text,
                    request_id=request_id,
                ),
            ),
        )
    except BaseException:
        current = await store.load(session_id)
        await runner.interrupt_turn(
            turn,
            expected_session_version=current.session_version,
            failure=_entry_failure(request_id),
        )
        raise


def _entry_assistant_message(result: object) -> AIMessage:
    if not isinstance(result, Mapping):
        raise EntryConversationError("The entry agent returned an invalid result.")
    messages = result.get("messages")
    if (
        not isinstance(messages, (list, tuple))
        or len(messages) != 1
        or not isinstance(messages[0], AIMessage)
        or messages[0].tool_calls
        or not messages[0].text
    ):
        raise EntryConversationError("The entry agent returned an invalid greeting.")
    return messages[0]


def _entry_failure(request_id: str):
    return RouteDeckFailure(
        kind=FailureKind.INTERNAL,
        code="entry_greeting_interrupted",
        phase="agent_entry",
        correlation_id=request_id,
        request_id=request_id,
        public_message="The buyer greeting could not be completed.",
    )


__all__ = [
    "BuyerEntryAgent",
    "EntryConversationError",
    "start_home_conversation",
]
