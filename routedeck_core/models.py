from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

RouteDeckLane = str
RouteDeckActionKind = Literal["button", "chip", "form", "nav", "summary"]
RouteDeckActionEmphasis = Literal["primary", "secondary"]
RouteDeckActionCategory = Literal["auth", "setup", "navigation", "execution", "feedback", "learning"]
RouteDeckActionPlacement = Literal["next_best", "rail", "inline", "evidence"]
RouteDeckFieldType = Literal["text", "password", "select", "url", "textarea"]
RouteDeckSafetyClass = Literal[
    "navigation",
    "state_selection",
    "draft",
    "read_external",
    "write_external",
    "destructive",
    "credential",
    "admin",
]
RouteDeckExecutionMode = Literal["auto", "review", "blocked"]
RouteDeckInvocationKind = Literal["direct", "form", "entity_selector", "surface", "hidden"]
RouteDeckSurfaceRole = Literal["frame", "active", "diagnostic"]
RouteDeckRuntimeStatus = Literal["idle", "refreshing", "streaming", "dispatching", "recovering", "failed"]
RouteDeckEventType = Literal[
    "projection_update",
    "operation_started",
    "operation_completed",
    "graph_transition",
    "guard_failure",
    "surface_update",
    "runtime_status",
]


class RouteDeckFieldSpec(BaseModel):
    key: str
    label: str
    field_type: RouteDeckFieldType = "text"
    required: bool = False
    placeholder: str | None = None
    default: Any = None
    options: list[dict[str, str]] | None = None
    help_text: str | None = None
    validation_hint: str | None = None
    sensitive: bool = False


class RouteDeckActionSpec(BaseModel):
    id: str
    label: str
    capability_id: str | None = None
    description: str | None = None
    emphasis: RouteDeckActionEmphasis = "secondary"
    kind: RouteDeckActionKind = "button"
    category: RouteDeckActionCategory | None = None
    placement: RouteDeckActionPlacement | None = None
    fields: list[RouteDeckFieldSpec] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    invocation_kind: RouteDeckInvocationKind | None = None
    allowed_nodes: list[str] = Field(default_factory=list)
    visibility: Literal["contextual", "persistent", "dynamic"] = "contextual"
    recovery_prompt: str | None = None
    sensitive: bool = False


class RouteDeckNodeSpec(BaseModel):
    id: str
    label: str
    lane: RouteDeckLane
    description: str
    prompt_placeholder: str | None = None
    allowed_actions: list[str] = Field(default_factory=list)
    expected_input: str | None = None
    recovery_prompt: str | None = None
    parent: str | None = None
    allowed_surfaces: dict[str, list[str]] = Field(default_factory=dict)
    default_surfaces: dict[str, str] = Field(default_factory=dict)


class RouteDeckEdgeSpec(BaseModel):
    from_stage: str = Field(alias="from")
    to_stage: str = Field(alias="to")
    edge_type: str = Field(alias="type")
    condition: str | None = None
    explanation: str | None = None
    action_id: str | None = None

    model_config = {"populate_by_name": True}


class RouteDeckSensitivePolicy(BaseModel):
    masked_payload_keys: list[str] = Field(default_factory=list)
    chat_secret_fields: list[str] = Field(default_factory=list)
    url_or_modal_only_fields: list[str] = Field(default_factory=list)
    note: str


class RouteDeckManifest(BaseModel):
    version: str
    nodes: list[RouteDeckNodeSpec]
    edges: list[RouteDeckEdgeSpec]
    actions: list[RouteDeckActionSpec]
    policies: dict[str, Any] = Field(default_factory=dict)
    test_paths: list[dict[str, Any]] = Field(default_factory=list)


class RouteDeckRuntimeSnapshot(BaseModel):
    current_node: str | None = None
    reachable_nodes: list[str] = Field(default_factory=list)
    valid_actions: list[dict[str, Any]] = Field(default_factory=list)
    blocked_actions: list[dict[str, str]] = Field(default_factory=list)
    executed_nodes: list[str] = Field(default_factory=list)
    progress: dict[str, Any] = Field(default_factory=dict)
    recovery_prompts: list[str] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class RouteDeckOperation(BaseModel):
    id: str
    label: str
    description: str | None = None
    category: RouteDeckActionCategory | None = None
    kind: RouteDeckActionKind | None = None
    placement: RouteDeckActionPlacement | None = None
    emphasis: RouteDeckActionEmphasis = "secondary"
    safety_class: RouteDeckSafetyClass = "navigation"
    execution_mode: RouteDeckExecutionMode = "review"
    input_schema: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)
    invocation_kind: RouteDeckInvocationKind = "direct"
    can_dispatch_now: bool = True
    required_args: list[str] = Field(default_factory=list)
    missing_args: list[str] = Field(default_factory=list)
    guard: str | None = None
    target_node: str | None = None


class RouteDeckSurface(BaseModel):
    name: str
    component: str
    variant: str = "default"
    role: RouteDeckSurfaceRole = "frame"
    props: dict[str, Any] = Field(default_factory=dict)
    lifecycle: Literal["ephemeral", "stable"] = "ephemeral"


class RouteDeckProjection(BaseModel):
    current_context: str
    graph_node: str
    projection_version: int = 1
    legal_operations: list[RouteDeckOperation] = Field(default_factory=list)
    surfaces: dict[str, RouteDeckSurface] = Field(default_factory=dict)
    presentation_state: dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class RouteDeckEvent(BaseModel):
    event_type: RouteDeckEventType
    turn_id: str | None = None
    projection_version: int | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class RouteDeckRuntimeState(BaseModel):
    projection: RouteDeckProjection
    status: RouteDeckRuntimeStatus = "idle"
    graph_state: dict[str, Any] = Field(default_factory=dict)
    location: str | None = None
    last_event: RouteDeckEvent | None = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RouteDeckDispatchInput(BaseModel):
    operation_id: str
    args: dict[str, Any] = Field(default_factory=dict)
    graph_state: dict[str, Any] = Field(default_factory=dict)
    projection_version: int | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class RouteDeckDispatchResult(BaseModel):
    operation_id: str
    accepted: bool
    state: RouteDeckRuntimeState
    active_surface: RouteDeckSurface | None = None
    messages: list[dict[str, Any]] = Field(default_factory=list)
    events: list[RouteDeckEvent] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RouteDeckIntrospection(BaseModel):
    current_node: str | None = None
    reachable_nodes: list[str] = Field(default_factory=list)
    legal_operations: list[dict[str, Any]] = Field(default_factory=list)
    blocked_operations: list[dict[str, Any]] = Field(default_factory=list)
    guard_explanations: list[str] = Field(default_factory=list)
    surfaces: dict[str, Any] = Field(default_factory=dict)
    route_traces: list[dict[str, Any]] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
