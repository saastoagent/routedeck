from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

RouteDeckLane = Literal["system", "auth", "workspace", "terminal"]
RouteDeckActionKind = Literal["button", "chip", "form", "nav", "summary"]
RouteDeckActionEmphasis = Literal["primary", "secondary"]
RouteDeckActionCategory = Literal["auth", "setup", "navigation", "execution", "feedback", "learning"]
RouteDeckActionPlacement = Literal["next_best", "rail", "inline", "evidence"]
RouteDeckFieldType = Literal["text", "password", "select", "url"]


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
