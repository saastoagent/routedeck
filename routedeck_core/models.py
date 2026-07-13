from __future__ import annotations

from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, Field

RouteDeckLane = str
RouteDeckActionKind = Literal["button", "chip", "form", "nav", "summary"]
RouteDeckActionEmphasis = Literal["primary", "secondary"]
RouteDeckActionCategory = Literal[
    "auth", "setup", "navigation", "execution", "feedback", "learning", "deployment"
]
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
RouteDeckInvocationKind = Literal[
    "direct", "form", "entity_selector", "surface", "hidden"
]
RouteDeckSurfaceRole = Literal["frame", "active", "diagnostic"]
RouteDeckSurfaceKind = Literal["peer", "detail", "embedded"]
RouteDeckNodeKind = Literal["workflow", "section", "detail", "transient"]
RouteDeckDirtyPolicy = Literal["none", "confirm", "block"]
RouteDeckRuntimeStatus = Literal[
    "idle", "refreshing", "streaming", "dispatching", "recovering", "failed"
]
RouteDeckRuntimeEventType = Literal[
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
    node_kind: RouteDeckNodeKind = "workflow"
    capability_id: str | None = None
    show_in_navgraph: bool = True
    show_in_capability_rail: bool = True
    cancel_target_node: str | None = None
    dirty_policy: RouteDeckDirtyPolicy = "none"
    allowed_surfaces: dict[str, list[str]] = Field(default_factory=dict)
    default_surfaces: dict[str, str] = Field(default_factory=dict)


class RouteDeckEdgeSpec(BaseModel):
    from_stage: str = Field(alias="from")
    to_stage: str = Field(alias="to")
    edge_type: str = Field(alias="type")
    condition: str | None = None
    explanation: str | None = None
    action_id: str | None = None
    capability_id: str | None = None

    model_config = {"populate_by_name": True}


class RouteDeckCapabilitySpec(BaseModel):
    capability_id: str
    label: str
    operation_ids: list[str] = Field(default_factory=list)
    entity_kinds: list[str] = Field(default_factory=list)
    surface_ids: list[str] = Field(default_factory=list)
    chat_enabled: bool = True
    surface_enabled: bool = True
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RouteDeckEntityOperationBinding(BaseModel):
    operation_id: str
    args: dict[str, Any] = Field(default_factory=dict)


class RouteDeckAvailableEntity(BaseModel):
    kind: str
    entity_key: str
    label: str
    parent_label: str | None = None
    rendered_on: list[str] = Field(default_factory=list)
    operations: list[RouteDeckEntityOperationBinding] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RouteDeckBindingExpression(BaseModel):
    source: Literal["entity", "event"] = Field(alias="from")
    path: str

    model_config = {"populate_by_name": True, "serialize_by_alias": True}


class RouteDeckSurfaceAffordance(BaseModel):
    surface_id: str
    affordance_id: str
    event: str
    capability_id: str | None = None
    operation_id: str | None = None
    entity_key: str | None = None
    entity_keys: list[str] = Field(default_factory=list)
    arg_bindings: dict[str, RouteDeckBindingExpression] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RouteDeckSurfaceInteractionEvent(BaseModel):
    surface_id: str
    affordance_id: str
    event: str | None = None
    entity_key: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class RouteDeckSemanticObservation(BaseModel):
    observation_type: str = Field(alias="type")
    summary: str
    entity_key: str | None = None
    operation_id: str | None = None
    accepted: bool | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True, "serialize_by_alias": True}


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
    capabilities: list[RouteDeckCapabilitySpec] = Field(default_factory=list)
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


class RouteDeckActionField(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=120)
    field_type: RouteDeckFieldType = "text"
    required: bool = False
    placeholder: str | None = Field(default=None, max_length=240)
    default: Any = None
    options: list[dict[str, str]] | None = None
    help_text: str | None = Field(default=None, max_length=300)
    validation_hint: str | None = Field(default=None, max_length=300)
    sensitive: bool = False


class RouteDeckActionCard(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=120)
    capability_id: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=240)
    emphasis: RouteDeckActionEmphasis = "secondary"
    kind: RouteDeckActionKind = "button"
    category: RouteDeckActionCategory | None = None
    placement: RouteDeckActionPlacement | None = None
    explanation: str | None = Field(default=None, max_length=500)
    recovery_prompt: str | None = Field(default=None, max_length=300)
    feedback_target: str | None = Field(default=None, max_length=160)
    fields: list[RouteDeckActionField] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    disabled_reason: str | None = Field(default=None, max_length=240)


class RouteDeckUIArtifact(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    kind: Literal["widget", "markup"]
    surface: Literal["inline", "canvas", "both"] = "inline"
    title: str | None = Field(default=None, max_length=160)
    widget_type: str | None = Field(default=None, max_length=120)
    payload: dict[str, Any] = Field(default_factory=dict)
    markup: str | None = Field(default=None, max_length=20_000)


class RouteDeckGraphMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str


class RouteDeckGraphManifestNode(BaseModel):
    id: str
    label: str
    lane: str
    parent: str | None = None
    description: str | None = None
    prompt_placeholder: str | None = None
    allowed_actions: list[str] = Field(default_factory=list)
    expected_input: str | None = None
    recovery_prompt: str | None = None


class RouteDeckGraphManifestEdge(BaseModel):
    from_stage: str = Field(alias="from")
    to_stage: str = Field(alias="to")
    type: str
    condition: str | None = None
    explanation: str | None = None
    action_id: str | None = None

    model_config = {"populate_by_name": True}


class RouteDeckGraphManifestAction(BaseModel):
    id: str
    label: str
    capability_id: str | None = None
    description: str | None = None
    emphasis: RouteDeckActionEmphasis = "secondary"
    kind: RouteDeckActionKind = "button"
    category: RouteDeckActionCategory | None = None
    placement: RouteDeckActionPlacement | None = None
    fields: list[RouteDeckActionField] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    allowed_nodes: list[str] = Field(default_factory=list)
    visibility: str = "contextual"
    recovery_prompt: str | None = None
    sensitive: bool = False


class RouteDeckGraphManifest(BaseModel):
    version: str
    nodes: list[RouteDeckGraphManifestNode] = Field(default_factory=list)
    edges: list[RouteDeckGraphManifestEdge] = Field(default_factory=list)
    actions: list[RouteDeckGraphManifestAction] = Field(default_factory=list)
    policies: dict[str, Any] = Field(default_factory=dict)
    test_paths: list[dict[str, Any]] = Field(default_factory=list)


class RouteDeckGraphNavigationLocation(BaseModel):
    node_id: str
    surface_id: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class RouteDeckGraphState(BaseModel):
    node: str = "home"
    active_surface_id: str | None = None
    route_params: dict[str, Any] = Field(default_factory=dict)
    navigation_back_stack: list[RouteDeckGraphNavigationLocation] = Field(
        default_factory=list
    )
    navigation_forward_stack: list[RouteDeckGraphNavigationLocation] = Field(
        default_factory=list
    )
    pending_operation_id: str | None = None
    pending_operation_args: dict[str, Any] = Field(default_factory=dict)
    dirty_surfaces: dict[str, bool] = Field(default_factory=dict)
    graph_context: dict[str, Any] = Field(default_factory=dict)
    executed_nodes: list[str] = Field(default_factory=list)


class RouteDeckGraphRequest(BaseModel):
    state: RouteDeckGraphState | None = None
    node_id: str | None = Field(default=None, max_length=120)
    selected_action_id: str | None = Field(default=None, max_length=160)
    action_payload: dict[str, Any] = Field(default_factory=dict)
    user_input: str | None = Field(default=None, max_length=8_000)


class RouteDeckContextLens(BaseModel):
    current_node: str
    working_on: str
    active_surface_id: str | None = None
    route_params: dict[str, Any] = Field(default_factory=dict)
    legal_operation_ids: list[str] = Field(default_factory=list)


class RouteDeckGraphResponse(BaseModel):
    state: RouteDeckGraphState
    graph_version: str
    graph_manifest: RouteDeckGraphManifest
    route_deck_snapshot: RouteDeckRuntimeSnapshot
    context_lens: RouteDeckContextLens
    available_actions: list[RouteDeckActionCard] = Field(default_factory=list)
    persistent_actions: list[RouteDeckActionCard] = Field(default_factory=list)
    ui_artifacts: list[RouteDeckUIArtifact] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    messages: list[RouteDeckGraphMessage] = Field(default_factory=list)
    replace_path: str | None = None


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
    capability_id: str | None = None
    surface_id: str | None = None


class RouteDeckDeepLink(BaseModel):
    url: str
    resumable: bool = True
    requires_auth: bool = False
    label: str | None = None


class RouteDeckLocation(BaseModel):
    node_id: str
    surface_id: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    deeplink: RouteDeckDeepLink | None = None


class RouteDeckNavigationState(BaseModel):
    current: RouteDeckLocation
    back_stack: list[RouteDeckLocation] = Field(default_factory=list)
    forward_stack: list[RouteDeckLocation] = Field(default_factory=list)
    can_back: bool = False
    can_forward: bool = False
    can_cancel: bool = False


class RouteDeckSurface(BaseModel):
    name: str
    surface_id: str | None = None
    component: str
    variant: str = "default"
    role: RouteDeckSurfaceRole = "frame"
    slot: str | None = None
    surface_kind: RouteDeckSurfaceKind = "embedded"
    label: str | None = None
    default: bool = False
    props: dict[str, Any] = Field(default_factory=dict)
    lifecycle: Literal["ephemeral", "stable"] = "ephemeral"


class RouteDeckNavGraphNode(BaseModel):
    id: str
    label: str
    surface_id: str | None = None
    deeplink: RouteDeckDeepLink | None = None
    capability_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RouteDeckNavGraphEdge(BaseModel):
    source: str = Field(
        validation_alias=AliasChoices("from", "source", "from_stage"),
        serialization_alias="from",
    )
    target: str = Field(
        validation_alias=AliasChoices("to", "target", "to_stage"),
        serialization_alias="to",
    )
    action_id: str | None = None
    capability_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True, "serialize_by_alias": True}


class RouteDeckNavGraph(BaseModel):
    current: RouteDeckLocation
    nodes: list[RouteDeckNavGraphNode] = Field(default_factory=list)
    edges: list[RouteDeckNavGraphEdge] = Field(default_factory=list)
    traversed: list[str] = Field(default_factory=list)
    reachable: list[str] = Field(default_factory=list)


class RouteDeckProjection(BaseModel):
    current_context: str
    graph_node: str
    projection_version: int = 1
    legal_operations: list[RouteDeckOperation] = Field(default_factory=list)
    surfaces: dict[str, RouteDeckSurface] = Field(default_factory=dict)
    presentation_state: dict[str, Any] = Field(default_factory=dict)
    navigation: RouteDeckNavigationState
    context_lens: RouteDeckContextLens | None = None
    capabilities: list[RouteDeckCapabilitySpec] = Field(default_factory=list)
    navgraph: RouteDeckNavGraph | None = None
    available_entities: list[RouteDeckAvailableEntity] = Field(default_factory=list)
    surface_affordances: list[RouteDeckSurfaceAffordance] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class RouteDeckEvent(BaseModel):
    event_type: RouteDeckRuntimeEventType
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
    operation_id: str | None = None
    surface_event: RouteDeckSurfaceInteractionEvent | None = None
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
