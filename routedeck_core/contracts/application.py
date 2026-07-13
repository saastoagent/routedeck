from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .agent import AgentPolicyRef
from .navigation import (
    NavigationPolicySpec,
    NodeKind,
    NodeRef,
    RecoveryPolicySpec,
    RouteSpec,
    TransitionSpec,
)
from .operations import (
    ContextProviderSpec,
    EntityProviderSpec,
    GuardSpec,
    OperationRef,
    OperationSpec,
)
from .projection import FrozenJsonObject
from .surfaces import SurfaceRef, SurfaceSlotsSpec
from .suggestions import SuggestedActionSpec


class _FrozenContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CapabilityRef(_FrozenContract):
    id: str = Field(min_length=1)


class CapabilitySpec(_FrozenContract):
    id: str = Field(min_length=1)
    title: str
    operations: tuple[OperationRef, ...] = ()
    surfaces: tuple[SurfaceRef, ...] = ()
    policy_refs: tuple[AgentPolicyRef, ...] = ()

    @property
    def ref(self) -> CapabilityRef:
        return CapabilityRef(id=self.id)


class RouteParameterBinding(_FrozenContract):
    """Bind one declared route parameter to one operation argument exactly."""

    parameter: str = Field(min_length=1)
    argument: str = Field(min_length=1)


class RouteEntrySpec(_FrozenContract):
    """Declare the operation and outcome that authoritatively enter one route."""

    operation: OperationRef
    outcome: str = Field(min_length=1)
    bindings: tuple[RouteParameterBinding, ...] = ()


class NodeSpec(_FrozenContract):
    id: str = Field(min_length=1)
    title: str
    kind: NodeKind
    parent: NodeRef | None = None
    route: RouteSpec
    entry: RouteEntrySpec | None = None
    context_providers: tuple[ContextProviderSpec, ...] = ()
    entity_providers: tuple[EntityProviderSpec, ...] = ()
    guards: tuple[GuardSpec, ...] = ()
    operations: tuple[OperationSpec, ...] = ()
    capabilities: tuple[CapabilitySpec, ...] = ()
    surfaces: SurfaceSlotsSpec
    policy_refs: tuple[AgentPolicyRef, ...] = ()
    suggested_actions: tuple[SuggestedActionSpec, ...] = ()
    navigation: NavigationPolicySpec = NavigationPolicySpec()
    recovery: RecoveryPolicySpec = RecoveryPolicySpec()
    public_metadata: FrozenJsonObject = Field(
        default_factory=lambda: FrozenJsonObject({})
    )

    def public_metadata_value(self) -> dict[str, object]:
        return self.public_metadata.to_dict()

    @property
    def ref(self) -> NodeRef:
        return NodeRef(id=self.id)


class CompiledApplicationSpec(_FrozenContract):
    name: str = Field(min_length=1)
    entry_node: NodeRef
    nodes: tuple[NodeSpec, ...]
    transitions: tuple[TransitionSpec, ...]


__all__ = [
    "CapabilityRef",
    "CapabilitySpec",
    "CompiledApplicationSpec",
    "NodeSpec",
    "RouteEntrySpec",
    "RouteParameterBinding",
]
