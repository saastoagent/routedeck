from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, NoReturn, Protocol

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from routedeck_core.contracts.conversation import ConversationRole
from routedeck_core.ports import (
    AgentReviewRequired,
    AgentTurnCompleted,
    AssistantTextDelta,
    AssistantTextReset,
    RouteDeckAgentEvent,
    RouteDeckAgentStreamError,
    RouteDeckAgentTurn,
)
from routedeck_core.supervision import RouteDeckOperationRunner
from routedeck_langgraph import RouteDeckInvocationContext, extract_conversation_turns

from .turn_policy import TURN_POLICY_EVENT_TAG


class AgentEventStream(Protocol):
    def astream_events(
        self,
        input: Mapping[str, Any],
        config: Mapping[str, Any] | None = None,
        *,
        version: str = "v2",
        **kwargs: Any,
    ) -> AsyncIterator[Mapping[str, Any]]: ...


@dataclass(frozen=True)
class _CompletedModelRun:
    output: AIMessage
    chunks: tuple[str, ...]


@dataclass(frozen=True)
class MedusaLangGraphAgentDriver:
    """Translate Medusa's LangGraph events into RouteDeck conversation events."""

    agent: AgentEventStream
    runner: RouteDeckOperationRunner

    def __post_init__(self) -> None:
        if not callable(getattr(self.agent, "astream_events", None)):
            raise TypeError("Medusa agent must expose astream_events")

    async def stream(
        self,
        turn: RouteDeckAgentTurn,
    ) -> AsyncIterator[RouteDeckAgentEvent]:
        invocation_context: RouteDeckInvocationContext = {
            "session_id": turn.session_id,
            "request_id_prefix": turn.request_id,
            "turn": turn.turn,
            "review_turns": (turn.user_turn,),
        }
        final_messages: tuple[BaseMessage, ...] | None = None
        model_chunks: dict[str, list[str]] = {}
        exposed_model_runs: set[str] = set()
        tool_calling_model_runs: set[str] = set()
        completed_model_runs: list[_CompletedModelRun] = []
        event_stream = self.agent.astream_events(
            {
                "messages": [
                    HumanMessage(content=turn.message, id=turn.user_turn.turn_id)
                ]
            },
            version="v2",
            context=invocation_context,
        )
        async for event in event_stream:
            if _is_internal_turn_policy_event(event):
                continue
            event_name = event.get("event")
            data = event.get("data")
            if not isinstance(data, Mapping):
                _invalid("The Medusa agent returned an invalid streaming event.")

            if event_name == "on_chat_model_end":
                output = data.get("output")
                if isinstance(output, AIMessage) and len(output.tool_calls) > 1:
                    raise RouteDeckAgentStreamError(
                        "parallel_tool_calls_rejected",
                        "The Medusa agent attempted parallel tool calls.",
                    )
                if isinstance(output, AIMessage):
                    run_id = _model_run_id(event)
                    if output.tool_calls and run_id in exposed_model_runs:
                        exposed_model_runs.remove(run_id)
                        yield AssistantTextReset()
                    completed_model_runs.append(
                        _CompletedModelRun(
                            output=output,
                            chunks=tuple(model_chunks.pop(run_id, ())),
                        )
                    )

            if event_name == "on_chat_model_stream":
                chunk = data.get("chunk")
                run_id = _model_run_id(event)
                if getattr(chunk, "tool_call_chunks", ()):
                    tool_calling_model_runs.add(run_id)
                    if run_id in exposed_model_runs:
                        exposed_model_runs.remove(run_id)
                        yield AssistantTextReset()
                chunk_text = _message_text(chunk)
                if chunk_text:
                    model_chunks.setdefault(run_id, []).append(chunk_text)
                    if run_id not in tool_calling_model_runs:
                        exposed_model_runs.add(run_id)
                        yield AssistantTextDelta(chunk_text)

            event_output = data.get("output")
            candidate = _messages_from_output(event_output)
            review = _review_event(event_output)
            if review is None and candidate is not None:
                review = next(
                    (
                        payload
                        for message in candidate
                        if (payload := _review_event(message)) is not None
                    ),
                    None,
                )
            if review is not None:
                await _close_event_stream(event_stream)
                yield review
                return

            if event_name == "on_chain_end" and candidate is not None:
                final_messages = candidate

        if final_messages is None:
            raise RouteDeckAgentStreamError(
                "agent_result_missing",
                "The Medusa agent did not return a final response.",
            )

        review = next(
            (
                payload
                for message in final_messages
                if (payload := _review_event(message)) is not None
            ),
            None,
        )
        if review is not None:
            yield review
            return

        assistant_message = _final_assistant_message(final_messages)
        assistant_text = (
            _message_text(assistant_message) if assistant_message is not None else ""
        )
        if assistant_message is None or not assistant_text:
            raise RouteDeckAgentStreamError(
                "assistant_response_empty",
                "The Medusa agent returned an empty response.",
            )
        extracted = extract_conversation_turns(
            final_messages,
            current_user_turn=turn.user_turn,
            id_factory=self.runner.id_factory,
        )
        if (
            not extracted.turns
            or extracted.turns[-1].role is not ConversationRole.ASSISTANT
            or extracted.turns[-1].content != assistant_text
        ):
            raise RouteDeckAgentStreamError(
                "agent_history_invalid",
                "The Medusa agent returned invalid conversation history.",
            )
        assistant_turn = extracted.turns[-1]
        if not _final_assistant_was_streamed(
            assistant_message,
            completed_model_runs,
        ):
            raise RouteDeckAgentStreamError(
                "assistant_stream_missing",
                "The Medusa agent did not stream its final response.",
            )
        yield AgentTurnCompleted(
            turns=extracted.turns,
            assistant_turn_id=assistant_turn.turn_id,
        )


def _is_internal_turn_policy_event(event: Mapping[str, object]) -> bool:
    tags = event.get("tags")
    return isinstance(tags, (list, tuple)) and TURN_POLICY_EVENT_TAG in tags


def _final_assistant_message(
    messages: Sequence[BaseMessage],
) -> AIMessage | None:
    for message in reversed(messages):
        if isinstance(message, AIMessage) and not message.tool_calls:
            return message
    return None


def _final_assistant_was_streamed(
    assistant: AIMessage,
    completed_runs: Sequence[_CompletedModelRun],
) -> bool:
    assistant_text = _message_text(assistant)
    return any(
        not run.output.tool_calls
        and _message_text(run.output) == assistant_text
        and bool(run.chunks)
        and "".join(run.chunks) == assistant_text
        for run in completed_runs
    )


def _model_run_id(event: Mapping[str, Any]) -> str:
    run_id = event.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        _invalid("The Medusa agent returned an invalid streaming event.")
    return run_id


def _message_text(message: object) -> str:
    return message.text if isinstance(message, BaseMessage) else ""


def _messages_from_output(output: object) -> tuple[BaseMessage, ...] | None:
    if not isinstance(output, Mapping):
        return None
    messages = output.get("messages")
    if not isinstance(messages, (list, tuple)) or any(
        not isinstance(message, BaseMessage) for message in messages
    ):
        return None
    return tuple(messages)


def _review_event(value: object) -> AgentReviewRequired | None:
    if not isinstance(value, ToolMessage) or not isinstance(value.artifact, Mapping):
        return None
    if value.artifact.get("disposition") != "requires_review":
        return None
    review = value.artifact.get("review")
    operation_id = value.artifact.get("operation_id")
    if not isinstance(review, Mapping) or not isinstance(operation_id, str):
        _invalid_review()
    review_id = review.get("id")
    expires_at = review.get("expires_at")
    if not isinstance(review_id, str) or not isinstance(expires_at, str):
        _invalid_review()
    try:
        expiry = datetime.fromisoformat(expires_at)
    except ValueError:
        _invalid_review()
    if expiry.tzinfo is None:
        _invalid_review()
    return AgentReviewRequired(
        operation_id=operation_id,
        review_id=review_id,
        expires_at=expiry,
    )


async def _close_event_stream(stream: object) -> None:
    close = getattr(stream, "aclose", None)
    if close is not None and callable(close):
        await close()


def _invalid(message: str) -> NoReturn:
    raise RouteDeckAgentStreamError("agent_stream_contract_invalid", message)


def _invalid_review() -> NoReturn:
    raise RouteDeckAgentStreamError(
        "review_result_invalid",
        "The Medusa agent returned an invalid review result.",
    )


__all__ = ["AgentEventStream", "MedusaLangGraphAgentDriver"]
