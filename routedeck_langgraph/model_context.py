from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from pydantic import BaseModel, ConfigDict, Field

from routedeck_core.app import BoundRouteDeckApp, CompiledRouteDeckApp
from routedeck_core.context import AgentContextLens
from routedeck_core.contracts.conversation import (
    ConversationRole,
    ConversationToolCall,
    ConversationTurnStatus,
)
from routedeck_core.contracts.operations import OperationDisposition, OperationSpec
from routedeck_core.contracts.projection import DataClassification, FrozenJson
from routedeck_core.contracts.session import (
    ReviewResolution,
    RouteDeckSession,
    SessionSnapshot,
)
from routedeck_core.validation import RouteDeckValidationError


class _FrozenContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ModelContextValue(_FrozenContract):
    name: str = Field(min_length=1)
    value: FrozenJson


class ModelContextSurface(_FrozenContract):
    surface_id: str = Field(min_length=1)
    component: str = Field(min_length=1)
    values: tuple[ModelContextValue, ...] = ()


class ModelContextEntity(_FrozenContract):
    entity_kind: str = Field(min_length=1)
    handle: str = Field(min_length=1)
    values: tuple[ModelContextValue, ...] = ()


class ModelContextTool(_FrozenContract):
    name: str = Field(min_length=1)
    title: str
    description: str
    input_schema: dict[str, Any]
    safety_class: str
    review_required: bool


class ModelContextStatus(_FrozenContract):
    code: str = Field(min_length=1)
    message: str | None = None
    needs_input: bool = False
    review_pending: bool = False


class ModelContextObservation(_FrozenContract):
    request_id: str
    content: str


class ModelContextPolicy(_FrozenContract):
    policy_id: str = Field(min_length=1)
    instruction: str = Field(min_length=1)


class ModelContextSuggestedAction(_FrozenContract):
    action_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


class RouteDeckModelContext(_FrozenContract):
    """The default-deny RouteDeck state made visible to one model call."""

    current_node: str = Field(min_length=1)
    active_surface: ModelContextSurface | None = None
    visible_entities: tuple[ModelContextEntity, ...] = ()
    legal_tools: tuple[ModelContextTool, ...] = ()
    suggested_actions: tuple[ModelContextSuggestedAction, ...] = ()
    policies: tuple[ModelContextPolicy, ...] = ()
    status: ModelContextStatus
    recent_observations: tuple[ModelContextObservation, ...] = ()


def build_model_context(
    snapshot: SessionSnapshot | RouteDeckSession,
    app: BoundRouteDeckApp | CompiledRouteDeckApp,
    *,
    observation_limit: int = 8,
) -> RouteDeckModelContext:
    """Project only current, public, operation-scoped state into model context.

    Private form values, private entity IDs, diagnostics, and unrelated
    conversation history are never emitted. Public handles and operation IDs
    from private bindings are consulted only to enforce the entity allowlist.
    """

    if observation_limit < 0:
        raise ValueError("observation_limit must be non-negative")
    session = snapshot.state if isinstance(snapshot, SessionSnapshot) else snapshot
    compiled = app.app if isinstance(app, BoundRouteDeckApp) else app
    resolved = AgentContextLens(compiled).resolve(session)
    node = resolved.node
    legal_operations = resolved.legal_operations

    surface_spec = resolved.active_surface
    public_surface = (
        next(
            (
                surface
                for surface in session.public_state.surface_state
                if surface.surface_id == surface_spec.id
            ),
            None,
        )
        if surface_spec is not None
        else None
    )
    surface_values: tuple[ModelContextValue, ...] = ()
    if public_surface is not None:
        surface_values = tuple(
            ModelContextValue(name=value.name, value=value.value)
            for value in public_surface.values
            if value.classification is DataClassification.PUBLIC
        )

    visible_entities: list[ModelContextEntity] = []
    for entity in resolved.visible_entities:
        visible_entities.append(
            ModelContextEntity(
                entity_kind=entity.entity_kind,
                handle=entity.handle,
                values=tuple(
                    ModelContextValue(name=value.name, value=value.value)
                    for value in entity.values
                ),
            )
        )

    observations = tuple(
        ModelContextObservation(
            request_id=turn.request_id or turn.turn_id,
            content=turn.content,
        )
        for turn in session.conversation
        if turn.status is ConversationTurnStatus.FINALIZED
        and turn.role is ConversationRole.TOOL
    )
    if observation_limit == 0:
        observations = ()
    else:
        observations = observations[-observation_limit:]

    review_pending = bool(
        session.operation is not None
        and session.operation.pending_review is not None
        and session.operation.pending_review.resolution is ReviewResolution.PENDING
    )
    status_code = session.public_state.status_code
    return RouteDeckModelContext(
        current_node=node.id,
        active_surface=(
            ModelContextSurface(
                surface_id=surface_spec.id,
                component=surface_spec.component,
                values=surface_values,
            )
            if surface_spec is not None
            else None
        ),
        visible_entities=tuple(visible_entities),
        legal_tools=tuple(_model_tool(operation) for operation in legal_operations),
        suggested_actions=tuple(
            ModelContextSuggestedAction(
                action_id=action.id,
                label=(
                    action.label
                    or next(
                        operation.title
                        for operation in legal_operations
                        if operation.id == action.operation_id
                    )
                ),
                operation_id=action.operation_id,
                arguments=action.arguments_value(),
            )
            for action in resolved.suggested_actions
        ),
        policies=tuple(
            ModelContextPolicy(
                policy_id=policy.id,
                instruction=policy.instruction,
            )
            for policy in resolved.policies
        ),
        status=ModelContextStatus(
            code=status_code,
            message=session.public_state.status_message,
            needs_input=status_code == OperationDisposition.NEEDS_INPUT.value,
            review_pending=review_pending,
        ),
        recent_observations=observations,
    )


def reconstruct_messages(
    snapshot: SessionSnapshot | RouteDeckSession,
    *,
    tool_name_factory: Callable[[str], str] | None = None,
) -> tuple[BaseMessage, ...]:
    """Rebuild request-scoped LangGraph history from finalized RouteDeck turns."""

    session = snapshot.state if isinstance(snapshot, SessionSnapshot) else snapshot
    resolve_tool_name = tool_name_factory or (lambda operation_id: operation_id)
    messages: list[BaseMessage] = []
    for turn in session.conversation:
        if turn.status is not ConversationTurnStatus.FINALIZED:
            continue
        if turn.role is ConversationRole.USER:
            messages.append(HumanMessage(content=turn.content, id=turn.turn_id))
        elif turn.role is ConversationRole.ASSISTANT:
            messages.append(AIMessage(content=turn.content, id=turn.turn_id))
        elif turn.role is ConversationRole.TOOL:
            tool_call = turn.tool_call
            if tool_call is None or turn.tool_status is None:
                raise RouteDeckValidationError(
                    "Durable tool turns require typed tool-call metadata"
                )
            tool_name = resolve_tool_name(tool_call.name)
            messages.append(
                _tool_call_envelope(
                    turn.turn_id,
                    tool_call,
                    tool_name=tool_name,
                )
            )
            messages.append(
                ToolMessage(
                    content=turn.content,
                    id=turn.turn_id,
                    name=tool_name,
                    status=turn.tool_status,
                    tool_call_id=tool_call.call_id,
                )
            )
    return tuple(messages)


def merge_reconstructed_messages(
    reconstructed: Iterable[BaseMessage],
    current: Iterable[BaseMessage],
) -> list[BaseMessage]:
    """Prepend durable history without duplicating messages already supplied."""

    reconstructed_messages = tuple(reconstructed)
    current_messages = tuple(current)
    current_ids = {
        message.id
        for message in current_messages
        if isinstance(message.id, str) and message.id
    }
    durable = [
        message
        for message in reconstructed_messages
        if not (
            isinstance(message.id, str) and message.id and message.id in current_ids
        )
    ]
    return [*durable, *current_messages]


def _tool_call_envelope(
    turn_id: str,
    tool_call: ConversationToolCall,
    *,
    tool_name: str,
) -> AIMessage:
    return AIMessage(
        content=tool_call.assistant_content,
        id=f"{turn_id}:tool-call",
        tool_calls=[
            {
                "name": tool_name,
                "args": dict(tool_call.arguments),
                "id": tool_call.call_id,
                "type": "tool_call",
            }
        ],
    )


def _model_tool(operation: OperationSpec) -> ModelContextTool:
    return ModelContextTool(
        name=operation.id,
        title=operation.title,
        description=operation.description,
        input_schema=operation.input_schema_value(),
        safety_class=operation.safety_class.value,
        review_required=operation.review_policy.value == "required",
    )


__all__ = [
    "ModelContextEntity",
    "ModelContextObservation",
    "ModelContextPolicy",
    "ModelContextSuggestedAction",
    "ModelContextStatus",
    "ModelContextSurface",
    "ModelContextTool",
    "ModelContextValue",
    "RouteDeckModelContext",
    "build_model_context",
    "merge_reconstructed_messages",
    "reconstruct_messages",
]
