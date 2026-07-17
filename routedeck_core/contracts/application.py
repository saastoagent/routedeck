from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field

from .agent import AgentPolicyRef
from .navigation import (
    CompiledTransition,
    NavigationPolicy,
    NodeKind,
    NodeRef,
    RecoveryPolicy,
    Route,
    Transition,
)
from .operations import (
    ContextProvider,
    EntityProvider,
    Guard,
    OperationRef,
    Operation,
)
from .projection import FrozenJsonObject
from .surfaces import SurfaceRef, SurfaceSlots
from .suggestions import SuggestedAction


class _FrozenContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CapabilityRef(_FrozenContract):
    id: str = Field(min_length=1)


class Capability(_FrozenContract):
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


class RouteEntry(_FrozenContract):
    """Declare the operation and outcome that authoritatively enter one route."""

    operation: OperationRef
    outcome: str = Field(min_length=1)
    bindings: tuple[RouteParameterBinding, ...] = ()


class Node(_FrozenContract):
    id: str = Field(min_length=1)
    title: str
    kind: NodeKind
    parent: NodeRef | None = None
    route: Route
    entry: RouteEntry | None = None
    context_providers: tuple[ContextProvider, ...] = ()
    entity_providers: tuple[EntityProvider, ...] = ()
    guards: tuple[Guard, ...] = ()
    operations: tuple[Operation, ...] = ()
    outgoing: tuple[Transition, ...] = ()
    capabilities: tuple[Capability, ...] = ()
    surfaces: SurfaceSlots
    policy_refs: tuple[AgentPolicyRef, ...] = ()
    suggested_actions: tuple[SuggestedAction, ...] = ()
    navigation: NavigationPolicy = NavigationPolicy()
    recovery: RecoveryPolicy = RecoveryPolicy()
    public_metadata: FrozenJsonObject = Field(
        default_factory=lambda: FrozenJsonObject({})
    )

    def public_metadata_value(self) -> dict[str, object]:
        return self.public_metadata.to_dict()

    @property
    def ref(self) -> NodeRef:
        return NodeRef(id=self.id)


class CompiledGraph(_FrozenContract):
    name: str = Field(min_length=1)
    entry_node: NodeRef
    nodes: tuple[Node, ...]
    transitions: tuple[CompiledTransition, ...]
    incoming: Mapping[str, tuple[CompiledTransition, ...]]


__all__ = [
    "CapabilityRef",
    "Capability",
    "CompiledGraph",
    "Node",
    "RouteEntry",
    "RouteParameterBinding",
]
