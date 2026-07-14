from __future__ import annotations

import asyncio
import logging
import secrets
from collections.abc import AsyncIterator
from typing import NoReturn

from routedeck_core.contracts.conversation import (
    ConversationRole,
    FinalizedConversationTurn,
)
from routedeck_core.contracts.failures import FailureKind, RouteDeckFailure
from routedeck_core.contracts.session import SessionSnapshot
from routedeck_core.ports import (
    AgentReviewRequired,
    AgentTurnCompleted,
    AssistantTextDelta,
    AssistantTextReset,
    RouteDeckAgentStreamError,
    RouteDeckAgentTurn,
)
from routedeck_core.state.leases import TurnClaim, TurnLease, TurnOwnerKind

from .contracts import ChatStreamRequest
from .conversation_dependencies import RouteDeckConversationDependencies
from .conversation_projection import public_conversation
from .conversation_replay import chat_fingerprint, sse
from .dependencies import RouteDeckDependencyUnavailable


_LOGGER = logging.getLogger(__name__)


async def stream_agent_chat(
    *,
    dependencies: RouteDeckConversationDependencies,
    session_id: str,
    request: ChatStreamRequest,
    initial_snapshot: SessionSnapshot | None = None,
) -> AsyncIterator[str]:
    """Own one durable conversation turn around an injected product driver."""

    routedeck = dependencies.routedeck
    if dependencies.agent is None:
        raise RouteDeckDependencyUnavailable(
            "RouteDeck conversation agent is not configured"
        )
    agent = dependencies.agent
    runner = routedeck.runner
    snapshot = initial_snapshot or await routedeck.store.load(session_id)
    turn: TurnLease | None = None
    turn_active = False
    finalized = False
    user_turn = FinalizedConversationTurn(
        turn_id=runner.id_factory("turn"),
        role=ConversationRole.USER,
        content=request.message,
        request_id=request.request_id,
    )
    try:
        turn = await runner.begin_turn(
            TurnClaim(
                session_id=session_id,
                expected_session_version=request.expected_session_version,
                request_id=request.request_id,
                request_fingerprint=chat_fingerprint(request),
                owner_kind=TurnOwnerKind.CHAT,
            )
        )
        turn_active = True
        yield sse(
            "stream_start",
            {
                "request_id": request.request_id,
                "session_version": snapshot.session_version,
            },
        )
        yield sse(
            "conversation_snapshot",
            {"turns": public_conversation(snapshot)},
        )
        yield sse(
            "user_message",
            {
                "content": request.message,
                "request_id": request.request_id,
                "turn_id": user_turn.turn_id,
            },
        )

        event_stream = agent.stream(
            RouteDeckAgentTurn(
                session_id=session_id,
                request_id=request.request_id,
                message=request.message,
                turn=turn,
                user_turn=user_turn,
            )
        )
        async for event in event_stream:
            if isinstance(event, AssistantTextDelta):
                if not event.content:
                    _invalid_agent_event("The agent emitted an empty text delta.")
                yield sse(
                    "assistant_delta",
                    {"content": event.content, "request_id": request.request_id},
                )
                continue
            if isinstance(event, AssistantTextReset):
                yield sse("assistant_reset", {"request_id": request.request_id})
                continue
            if isinstance(event, AgentReviewRequired):
                turn_active = False
                await _close_event_stream(event_stream)
                yield sse(
                    "review_required",
                    {
                        "expires_at": event.expires_at.isoformat(),
                        "operation_id": event.operation_id,
                        "review_id": event.review_id,
                        "status": "requires_review",
                    },
                )
                yield sse(
                    "stream_end",
                    {"request_id": request.request_id, "status": "requires_review"},
                )
                return
            if isinstance(event, AgentTurnCompleted):
                current = await routedeck.store.load(session_id)
                completed = await runner.complete_turn(
                    turn,
                    expected_session_version=current.session_version,
                    turns=event.turns,
                )
                finalized = True
                turn_active = False
                yield sse(
                    "assistant_end",
                    {
                        "request_id": request.request_id,
                        "session_version": completed.session_version,
                        "projection_version": completed.projection_version,
                        "turn_id": event.assistant_turn_id,
                    },
                )
                yield sse(
                    "stream_end",
                    {"request_id": request.request_id, "status": "completed"},
                )
                return
            _invalid_agent_event(
                "The agent emitted an unsupported conversation event."
            )
        raise RouteDeckAgentStreamError(
            "agent_result_missing",
            "The agent did not return a terminal response.",
        )
    except asyncio.CancelledError:
        if turn is not None and turn_active and not finalized:
            await asyncio.shield(
                _interrupt_turn(
                    dependencies=dependencies,
                    turn=turn,
                    request_id=request.request_id,
                )
            )
        raise
    except Exception as error:
        interruption_persistence_failed = False
        if turn is not None and turn_active and not finalized:
            try:
                await _interrupt_turn(
                    dependencies=dependencies,
                    turn=turn,
                    request_id=request.request_id,
                )
            except Exception as interrupt_error:
                _log_failure(
                    "routedeck_chat_interrupt_failed",
                    request_id=request.request_id,
                    error=interrupt_error,
                )
                interruption_persistence_failed = True
        _log_failure(
            "routedeck_chat_stream_failed",
            request_id=request.request_id,
            error=error,
        )
        if interruption_persistence_failed:
            yield sse(
                "stream_end",
                {"request_id": request.request_id, "status": "outcome_unknown"},
            )
            return
        code = (
            error.code
            if isinstance(error, RouteDeckAgentStreamError)
            else "agent_error"
        )
        message = (
            error.public_message
            if isinstance(error, RouteDeckAgentStreamError)
            else "The agent could not complete this turn."
        )
        yield sse("chat_error", {"code": code, "message": message})
        yield sse(
            "stream_end",
            {"request_id": request.request_id, "status": "turn_interrupted"},
        )


async def _close_event_stream(stream: object) -> None:
    close = getattr(stream, "aclose", None)
    if close is not None and callable(close):
        await close()


async def _interrupt_turn(
    *,
    dependencies: RouteDeckConversationDependencies,
    turn: TurnLease,
    request_id: str,
) -> None:
    routedeck = dependencies.routedeck
    current = await routedeck.store.load(turn.session_id)
    await routedeck.runner.interrupt_turn(
        turn,
        expected_session_version=current.session_version,
        failure=RouteDeckFailure(
            kind=FailureKind.INTERNAL,
            code="turn_interrupted",
            phase="agent_stream",
            correlation_id=secrets.token_urlsafe(12),
            request_id=request_id,
            public_message="The agent turn was interrupted.",
        ),
    )


def _invalid_agent_event(message: str) -> NoReturn:
    raise RouteDeckAgentStreamError("agent_stream_contract_invalid", message)


def _log_failure(
    event: str,
    *,
    request_id: str,
    error: BaseException,
) -> None:
    error_type = type(error).__name__
    _LOGGER.error(
        "%s error_type=%s",
        event,
        error_type,
        extra={"request_id": request_id, "error_type": error_type},
    )


__all__ = ["stream_agent_chat"]
