from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

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


class _FrozenContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CapabilityRef(_FrozenContract):
    id: str = Field(min_length=1)


class CapabilitySpec(_FrozenContract):
    id: str = Field(min_length=1)
    title: str
    operations: tuple[OperationRef, ...] = ()
    surfaces: tuple[SurfaceRef, ...] = ()

    @property
    def ref(self) -> CapabilityRef:
        return CapabilityRef(id=self.id)


class NodeSpec(_FrozenContract):
    id: str = Field(min_length=1)
    title: str
    kind: NodeKind
    parent: NodeRef | None = None
    route: RouteSpec
    context_providers: tuple[ContextProviderSpec, ...] = ()
    entity_providers: tuple[EntityProviderSpec, ...] = ()
    guards: tuple[GuardSpec, ...] = ()
    operations: tuple[OperationSpec, ...] = ()
    capabilities: tuple[CapabilitySpec, ...] = ()
    surfaces: SurfaceSlotsSpec
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
]
