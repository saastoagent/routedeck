from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from routedeck_core.contracts.conversation import (
    ConversationRole,
    ConversationToolCall,
    FinalizedConversationTurn,
)
from routedeck_core.contracts.projection import FrozenJsonObject
from routedeck_core.validation import RouteDeckValidationError


@dataclass(frozen=True)
class ExtractedConversation:
    turns: tuple[FinalizedConversationTurn, ...]
    pending_tool_call: ConversationToolCall | None = None


def extract_conversation_turns(
    messages: Sequence[BaseMessage],
    *,
    current_user_turn: FinalizedConversationTurn,
    id_factory: Callable[[str], str],
    pending_tool_call_id: str | None = None,
) -> ExtractedConversation:
    """Extract one exact request suffix into framework-neutral durable turns."""

    if current_user_turn.role is not ConversationRole.USER:
        raise RouteDeckValidationError(
            "Current conversation marker must be a user turn"
        )
    if current_user_turn.request_id is None:
        raise RouteDeckValidationError("Current user turn requires a request ID")

    marker_indexes = [
        index
        for index, message in enumerate(messages)
        if isinstance(message, HumanMessage) and message.id == current_user_turn.turn_id
    ]
    if len(marker_indexes) != 1:
        raise RouteDeckValidationError(
            "Agent messages must contain exactly one current user-turn marker"
        )
    marker_index = marker_indexes[0]
    marker = messages[marker_index]
    if marker.text != current_user_turn.content:
        raise RouteDeckValidationError(
            "Current user-turn marker content does not match durable input"
        )

    turns: list[FinalizedConversationTurn] = [current_user_turn]
    unobserved: dict[str, ConversationToolCall] = {}
    for message in messages[marker_index + 1 :]:
        if isinstance(message, HumanMessage):
            raise RouteDeckValidationError(
                "One agent request cannot contain a second user turn"
            )
        if isinstance(message, AIMessage):
            if message.tool_calls:
                if unobserved:
                    raise RouteDeckValidationError(
                        "A new tool call arrived before the prior observation"
                    )
                if len(message.tool_calls) != 1:
                    raise RouteDeckValidationError(
                        "RouteDeck conversation extraction requires serial tool calls"
                    )
                call = _conversation_tool_call(message)
                if call.call_id in unobserved:
                    raise RouteDeckValidationError(
                        f"Duplicate unobserved tool call ID: {call.call_id}"
                    )
                unobserved[call.call_id] = call
                continue
            if unobserved:
                raise RouteDeckValidationError(
                    "Assistant response arrived before its tool observation"
                )
            turns.append(
                FinalizedConversationTurn(
                    turn_id=_message_turn_id(message, id_factory),
                    role=ConversationRole.ASSISTANT,
                    content=message.text,
                    request_id=current_user_turn.request_id,
                )
            )
            continue
        if isinstance(message, ToolMessage):
            tool_call = unobserved.pop(message.tool_call_id, None)
            if tool_call is None:
                raise RouteDeckValidationError(
                    f"Tool observation has no matching call: {message.tool_call_id}"
                )
            if message.name is not None and message.name != tool_call.name:
                raise RouteDeckValidationError(
                    "Tool observation name does not match its call envelope"
                )
            tool_call = _durable_tool_call(tool_call, message)
            turns.append(
                FinalizedConversationTurn(
                    turn_id=_message_turn_id(message, id_factory),
                    role=ConversationRole.TOOL,
                    content=message.text,
                    request_id=current_user_turn.request_id,
                    tool_call=tool_call,
                    tool_status=message.status,
                )
            )
            continue
        raise RouteDeckValidationError(
            f"Unsupported agent message in durable turn: {type(message).__name__}"
        )

    if pending_tool_call_id is None:
        if unobserved:
            raise RouteDeckValidationError(
                "Agent result contains an unobserved tool call"
            )
        return ExtractedConversation(turns=tuple(turns))

    if set(unobserved) != {pending_tool_call_id}:
        raise RouteDeckValidationError(
            "Review staging requires exactly the active unobserved tool call"
        )
    return ExtractedConversation(
        turns=tuple(turns),
        pending_tool_call=unobserved[pending_tool_call_id],
    )


def messages_from_agent_state(state: object) -> tuple[BaseMessage, ...]:
    """Read the documented MessagesState shapes without guessing or coercion."""

    value: object
    if isinstance(state, Mapping):
        value = state.get("messages")
    elif isinstance(state, (list, tuple)):
        value = state
    else:
        value = getattr(state, "messages", None)
    if not isinstance(value, (list, tuple)) or any(
        not isinstance(message, BaseMessage) for message in value
    ):
        raise RouteDeckValidationError(
            "LangGraph tool state must expose a BaseMessage sequence"
        )
    return tuple(value)


def _conversation_tool_call(message: AIMessage) -> ConversationToolCall:
    call = message.tool_calls[0]
    call_id = call.get("id")
    name = call.get("name")
    arguments = call.get("args")
    if not isinstance(call_id, str) or not call_id:
        raise RouteDeckValidationError("Tool call ID must be a non-empty string")
    if not isinstance(name, str) or not name:
        raise RouteDeckValidationError("Tool call name must be a non-empty string")
    if not isinstance(arguments, Mapping):
        raise RouteDeckValidationError("Tool call arguments must be a JSON object")
    return ConversationToolCall(
        call_id=call_id,
        name=name,
        arguments=FrozenJsonObject(dict(arguments)),
        assistant_content=message.text,
    )


def _durable_tool_call(
    tool_call: ConversationToolCall,
    message: ToolMessage,
) -> ConversationToolCall:
    artifact = message.artifact
    if not isinstance(artifact, Mapping):
        return tool_call
    if artifact.get("type") != "routedeck_operation_result":
        return tool_call
    operation_id = artifact.get("operation_id")
    if not isinstance(operation_id, str) or not operation_id:
        raise RouteDeckValidationError(
            "RouteDeck tool observations require an operation ID"
        )
    return tool_call.model_copy(update={"name": operation_id})


def _message_turn_id(
    message: BaseMessage,
    id_factory: Callable[[str], str],
) -> str:
    return (
        message.id if isinstance(message.id, str) and message.id else id_factory("turn")
    )


__all__ = [
    "ExtractedConversation",
    "extract_conversation_turns",
    "messages_from_agent_state",
]
