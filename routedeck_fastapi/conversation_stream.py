from __future__ import annotations

import asyncio
import logging
import secrets
from collections.abc import AsyncIterator
from dataclasses import dataclass
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
    AssistantInitiatedTrigger,
    AssistantTextDelta,
    AssistantTextReset,
    RouteDeckAgentEvent,
    RouteDeckAgentStreamError,
    RouteDeckAgentTurn,
    RouteDeckConversationTrigger,
    UserMessageTrigger,
)
from routedeck_core.state.leases import TurnClaim, TurnLease, TurnOwnerKind

from .conversation_projection import public_conversation
from .conversation_replay import conversation_fingerprint, sse
from .dependencies import RouteDeckDependencies, RouteDeckDependencyUnavailable


_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConversationTurnRequest:
    request_id: str
    expected_session_version: int
    trigger: RouteDeckConversationTrigger

    def __post_init__(self) -> None:
        if not self.request_id or len(self.request_id) > 256:
            raise ValueError("conversation request ID must contain 1 to 256 characters")
        if self.expected_session_version < 0:
            raise ValueError("expected session version must be non-negative")
        if not isinstance(
            self.trigger,
            (UserMessageTrigger, AssistantInitiatedTrigger),
        ):
            raise TypeError("RouteDeck conversation trigger is invalid")


async def stream_agent_turn(
    *,
    dependencies: RouteDeckDependencies,
    session_id: str,
    request: ConversationTurnRequest,
    initial_snapshot: SessionSnapshot | None = None,
) -> AsyncIterator[str]:
    """Run one durable conversation lifecycle around a typed trigger."""

    if dependencies.agent_driver is None:
        raise RouteDeckDependencyUnavailable(
            "RouteDeck conversation agent is not configured"
        )
    agent = dependencies.agent_driver
    runner = dependencies.runner
    snapshot = initial_snapshot or await dependencies.store.load(session_id)
    turn: TurnLease | None = None
    event_stream: AsyncIterator[RouteDeckAgentEvent] | None = None
    turn_active = False
    finalized = False
    try:
        turn = await runner.begin_turn(
            TurnClaim(
                session_id=session_id,
                expected_session_version=request.expected_session_version,
                request_id=request.request_id,
                request_fingerprint=conversation_fingerprint(request.trigger),
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
        if isinstance(request.trigger, UserMessageTrigger):
            yield sse(
                "user_message",
                {
                    "content": request.trigger.message,
                    "request_id": request.request_id,
                    "turn_id": request.trigger.user_turn.turn_id,
                },
            )

        event_stream = agent.stream(
            RouteDeckAgentTurn(
                session_id=session_id,
                request_id=request.request_id,
                lease=turn,
                trigger=request.trigger,
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
                if isinstance(request.trigger, AssistantInitiatedTrigger):
                    _invalid_agent_event(
                        "An assistant-initiated turn cannot require review."
                    )
                await _close_event_stream(event_stream)
                event_stream = None
                turn_active = False
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
                _validate_completed_event(request.trigger, event)
                await _close_event_stream(event_stream)
                event_stream = None
                current = await dependencies.store.load(session_id)
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
        event_stream = None
        raise RouteDeckAgentStreamError(
            "agent_result_missing",
            "The agent did not return a terminal response.",
        )
    except asyncio.CancelledError:
        cleanup = asyncio.create_task(
            _cancelled_turn_cleanup(
                dependencies=dependencies,
                event_stream=event_stream,
                turn=turn if turn_active and not finalized else None,
                request_id=request.request_id,
            )
        )
        try:
            await asyncio.shield(cleanup)
        except asyncio.CancelledError:
            await cleanup
        raise
    except Exception as error:
        if event_stream is not None:
            try:
                await _close_event_stream(event_stream)
            except Exception as close_error:
                _log_failure(
                    "routedeck_conversation_stream_close_failed",
                    request_id=request.request_id,
                    error=close_error,
                )
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
                    "routedeck_conversation_interrupt_failed",
                    request_id=request.request_id,
                    error=interrupt_error,
                )
                interruption_persistence_failed = True
        _log_failure(
            "routedeck_conversation_stream_failed",
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


def _validate_completed_event(
    trigger: RouteDeckConversationTrigger,
    event: AgentTurnCompleted,
) -> None:
    turns = event.turns
    if (
        not turns
        or any(not isinstance(turn, FinalizedConversationTurn) for turn in turns)
        or turns[-1].role is not ConversationRole.ASSISTANT
        or turns[-1].turn_id != event.assistant_turn_id
        or not turns[-1].content
    ):
        _invalid_agent_event("The agent returned invalid finalized conversation turns.")
    request_id = turns[-1].request_id
    if request_id is None or any(turn.request_id != request_id for turn in turns):
        _invalid_agent_event("The agent returned conversation turns for another request.")
    if isinstance(trigger, AssistantInitiatedTrigger):
        if len(turns) != 1:
            _invalid_agent_event(
                "An assistant-initiated turn must finalize only one assistant turn."
            )
        return
    if (
        turns[0] != trigger.user_turn
        or sum(turn.role is ConversationRole.USER for turn in turns) != 1
    ):
        _invalid_agent_event(
            "A user-message turn must retain exactly its current user marker."
        )


async def _cancelled_turn_cleanup(
    *,
    dependencies: RouteDeckDependencies,
    event_stream: AsyncIterator[RouteDeckAgentEvent] | None,
    turn: TurnLease | None,
    request_id: str,
) -> None:
    if event_stream is not None:
        try:
            await _close_event_stream(event_stream)
        except Exception as close_error:
            _log_failure(
                "routedeck_conversation_cancel_close_failed",
                request_id=request_id,
                error=close_error,
            )
    if turn is not None:
        try:
            await _interrupt_turn(
                dependencies=dependencies,
                turn=turn,
                request_id=request_id,
            )
        except Exception as interrupt_error:
            _log_failure(
                "routedeck_conversation_cancel_interrupt_failed",
                request_id=request_id,
                error=interrupt_error,
            )


async def _close_event_stream(stream: object) -> None:
    close = getattr(stream, "aclose", None)
    if close is not None and callable(close):
        await close()


async def _interrupt_turn(
    *,
    dependencies: RouteDeckDependencies,
    turn: TurnLease,
    request_id: str,
) -> None:
    current = await dependencies.store.load(turn.session_id)
    await dependencies.runner.interrupt_turn(
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


__all__ = ["ConversationTurnRequest", "stream_agent_turn"]
