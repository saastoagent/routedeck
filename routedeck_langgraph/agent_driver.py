from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, NoReturn, Protocol

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from routedeck_core.contracts.conversation import ConversationRole
from routedeck_core.ports import (
    AgentReviewRequired,
    AgentTurnCompleted,
    AssistantInitiatedTrigger,
    AssistantTextDelta,
    AssistantTextReset,
    RouteDeckAgentDriver,
    RouteDeckAgentEvent,
    RouteDeckAgentStreamError,
    RouteDeckAgentTurn,
    UserMessageTrigger,
)
from routedeck_core.runtime import RouteDeckRuntimeServices

from .conversation import (
    ExtractedConversation,
    extract_assistant_initiated_turn,
    extract_conversation_turns,
)
from .tool_wrapper import RouteDeckInvocationContext


_LOGGER = logging.getLogger("uvicorn.error.routedeck.langgraph")
_MODEL_STARTED_EVENT = "routedeck_langgraph_model_started"


class LangGraphEventStream(Protocol):
    def astream_events(
        self,
        input: Mapping[str, Any],
        config: Mapping[str, Any] | None = None,
        *,
        version: str = "v2",
        **kwargs: Any,
    ) -> AsyncIterator[Mapping[str, Any]]: ...


@dataclass(frozen=True)
class RouteDeckLangGraphGraphs:
    user_message: LangGraphEventStream
    assistant_initiated: LangGraphEventStream
    ignored_event_tags: frozenset[str]

    def __post_init__(self) -> None:
        for graph in (self.user_message, self.assistant_initiated):
            if not callable(getattr(graph, "astream_events", None)):
                raise TypeError("RouteDeck LangGraph graphs must expose astream_events")
        if any(not tag for tag in self.ignored_event_tags):
            raise ValueError("ignored LangGraph event tags must be non-empty")


GraphFactory = Callable[
    [RouteDeckRuntimeServices],
    RouteDeckLangGraphGraphs | None,
]


@dataclass(frozen=True)
class RouteDeckLangGraphDriverFactory:
    graph_factory: GraphFactory

    def create(
        self,
        services: RouteDeckRuntimeServices,
    ) -> RouteDeckAgentDriver | None:
        graphs = self.graph_factory(services)
        if graphs is None:
            return None
        if not isinstance(graphs, RouteDeckLangGraphGraphs):
            raise TypeError(
                "RouteDeck LangGraph graph factory returned an invalid graph set"
            )
        return RouteDeckLangGraphAgentDriver(
            graphs=graphs,
            id_factory=services.id_factory,
        )


@dataclass(frozen=True)
class _CompletedModelRun:
    output: AIMessage
    chunks: tuple[str, ...]


@dataclass(frozen=True)
class RouteDeckLangGraphAgentDriver:
    """Translate product-supplied LangGraph events into RouteDeck events."""

    graphs: RouteDeckLangGraphGraphs
    id_factory: Callable[[str], str]

    async def stream(
        self,
        turn: RouteDeckAgentTurn,
    ) -> AsyncIterator[RouteDeckAgentEvent]:
        graph, graph_input, context = self._invocation(turn)
        final_messages: tuple[BaseMessage, ...] | None = None
        model_chunks: dict[str, list[str]] = {}
        exposed_model_runs: set[str] = set()
        tool_calling_model_runs: set[str] = set()
        completed_model_runs: list[_CompletedModelRun] = []
        event_stream = (
            graph.astream_events(graph_input, version="v2")
            if context is None
            else graph.astream_events(graph_input, version="v2", context=context)
        )
        try:
            async for event in event_stream:
                if event.get("event") == "on_chat_model_start":
                    _log_model_started(
                        request_id=turn.request_id,
                        langchain_run_id=_model_run_id(event),
                    )
                if self._is_ignored_event(event):
                    continue
                event_name = event.get("event")
                data = event.get("data")
                if not isinstance(data, Mapping):
                    _invalid("The product agent returned an invalid streaming event.")

                if event_name == "on_chat_model_end":
                    output = data.get("output")
                    if isinstance(output, AIMessage) and output.tool_calls:
                        if isinstance(turn.trigger, AssistantInitiatedTrigger):
                            raise RouteDeckAgentStreamError(
                                "assistant_initiated_tool_call_rejected",
                                "The assistant-initiated graph attempted a tool call.",
                            )
                        if len(output.tool_calls) > 1:
                            raise RouteDeckAgentStreamError(
                                "parallel_tool_calls_rejected",
                                "The product agent attempted parallel tool calls.",
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
                        if isinstance(turn.trigger, AssistantInitiatedTrigger):
                            raise RouteDeckAgentStreamError(
                                "assistant_initiated_tool_call_rejected",
                                "The assistant-initiated graph attempted a tool call.",
                            )
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
                    if isinstance(turn.trigger, AssistantInitiatedTrigger):
                        raise RouteDeckAgentStreamError(
                            "assistant_initiated_review_rejected",
                            "The assistant-initiated graph attempted to stage review.",
                        )
                    yield review
                    return

                if event_name == "on_chain_end" and candidate is not None:
                    final_messages = candidate
        finally:
            await _close_event_stream(event_stream)

        if final_messages is None:
            raise RouteDeckAgentStreamError(
                "agent_result_missing",
                "The product agent did not return a final response.",
            )

        assistant_message = _final_assistant_message(final_messages)
        assistant_text = (
            _message_text(assistant_message) if assistant_message is not None else ""
        )
        if assistant_message is None or not assistant_text:
            raise RouteDeckAgentStreamError(
                "assistant_response_empty",
                "The product agent returned an empty response.",
            )
        extracted = self._extract(turn, final_messages)
        if (
            not extracted.turns
            or extracted.turns[-1].role is not ConversationRole.ASSISTANT
            or extracted.turns[-1].content != assistant_text
        ):
            raise RouteDeckAgentStreamError(
                "agent_history_invalid",
                "The product agent returned invalid conversation history.",
            )
        assistant_turn = extracted.turns[-1]
        if not _final_assistant_was_streamed(
            assistant_message,
            completed_model_runs,
        ):
            raise RouteDeckAgentStreamError(
                "assistant_stream_missing",
                "The product agent did not stream its final response.",
            )
        yield AgentTurnCompleted(
            turns=extracted.turns,
            assistant_turn_id=assistant_turn.turn_id,
        )

    def _invocation(
        self,
        turn: RouteDeckAgentTurn,
    ) -> tuple[
        LangGraphEventStream,
        Mapping[str, Any],
        RouteDeckInvocationContext | None,
    ]:
        if isinstance(turn.trigger, UserMessageTrigger):
            return self._user_message_invocation(turn, turn.trigger)
        if isinstance(turn.trigger, AssistantInitiatedTrigger):
            return self._assistant_initiated_invocation(turn)
        _invalid("The RouteDeck conversation trigger is unsupported.")

    def _user_message_invocation(
        self,
        turn: RouteDeckAgentTurn,
        trigger: UserMessageTrigger,
    ) -> tuple[
        LangGraphEventStream,
        Mapping[str, Any],
        RouteDeckInvocationContext,
    ]:
        context: RouteDeckInvocationContext = {
            "session_id": turn.session_id,
            "request_id_prefix": turn.request_id,
            "turn": turn.lease,
            "review_turns": (trigger.user_turn,),
        }
        return (
            self.graphs.user_message,
            {
                "messages": [
                    HumanMessage(
                        content=trigger.message,
                        id=trigger.user_turn.turn_id,
                    )
                ]
            },
            context,
        )

    def _assistant_initiated_invocation(
        self,
        turn: RouteDeckAgentTurn,
    ) -> tuple[
        LangGraphEventStream,
        Mapping[str, Any],
        RouteDeckInvocationContext,
    ]:
        context: RouteDeckInvocationContext = {
            "session_id": turn.session_id,
            "request_id_prefix": turn.request_id,
            "turn": turn.lease,
            "review_turns": (),
        }
        return self.graphs.assistant_initiated, {"messages": []}, context

    def _extract(
        self,
        turn: RouteDeckAgentTurn,
        final_messages: Sequence[BaseMessage],
    ) -> ExtractedConversation:
        if isinstance(turn.trigger, UserMessageTrigger):
            return self._extract_user_message(turn.trigger, final_messages)
        if isinstance(turn.trigger, AssistantInitiatedTrigger):
            return self._extract_assistant_initiated(turn, final_messages)
        _invalid("The RouteDeck conversation trigger is unsupported.")

    def _extract_user_message(
        self,
        trigger: UserMessageTrigger,
        final_messages: Sequence[BaseMessage],
    ) -> ExtractedConversation:
        return extract_conversation_turns(
            final_messages,
            current_user_turn=trigger.user_turn,
            id_factory=self.id_factory,
        )

    def _extract_assistant_initiated(
        self,
        turn: RouteDeckAgentTurn,
        final_messages: Sequence[BaseMessage],
    ) -> ExtractedConversation:
        return extract_assistant_initiated_turn(
            final_messages,
            request_id=turn.request_id,
            id_factory=self.id_factory,
        )

    def _is_ignored_event(self, event: Mapping[str, Any]) -> bool:
        tags = event.get("tags")
        return isinstance(tags, (list, tuple)) and bool(
            self.graphs.ignored_event_tags.intersection(
                tag for tag in tags if isinstance(tag, str)
            )
        )


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
        _invalid("The product agent returned an invalid streaming event.")
    return run_id


def _log_model_started(*, request_id: str, langchain_run_id: str) -> None:
    _LOGGER.info(
        "%s request_id=%s langchain_run_id=%s",
        _MODEL_STARTED_EVENT,
        request_id,
        langchain_run_id,
        extra={
            "routedeck_event": _MODEL_STARTED_EVENT,
            "request_id": request_id,
            "langchain_run_id": langchain_run_id,
        },
    )


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
        "The product agent returned an invalid review result.",
    )


__all__ = [
    "GraphFactory",
    "LangGraphEventStream",
    "RouteDeckLangGraphAgentDriver",
    "RouteDeckLangGraphDriverFactory",
    "RouteDeckLangGraphGraphs",
]
