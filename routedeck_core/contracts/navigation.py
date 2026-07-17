from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from .operations import OperationRef
from .surfaces import SurfaceRef


class _FrozenContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class NodeKind(StrEnum):
    WORKFLOW = "workflow"
    SECTION = "section"
    DETAIL = "detail"
    TRANSIENT = "transient"


class DeepLinkPolicy(StrEnum):
    SHAREABLE = "shareable"
    SESSION_BOUND = "session_bound"


class DirtyStatePolicy(StrEnum):
    NONE = "none"
    CONFIRM = "confirm"
    BLOCK = "block"


class NodeRef(_FrozenContract):
    id: str = Field(min_length=1)

    @property
    def feature(self) -> str:
        return self.id.partition(".")[0]


class Route(_FrozenContract):
    template: str = Field(min_length=1)
    deep_link_policy: DeepLinkPolicy


class NavigationPolicy(_FrozenContract):
    dirty_state: DirtyStatePolicy = DirtyStatePolicy.NONE
    can_back: bool = True
    can_forward: bool = True
    can_cancel: bool = True
    cancel_target: NodeRef | None = None


class RecoveryPolicy(_FrozenContract):
    directives: tuple[str, ...] = ()
    failure_surface: SurfaceRef | None = None


class Transition(_FrozenContract):
    operation: OperationRef
    outcome: str = Field(min_length=1)
    target: NodeRef


class CompiledTransition(_FrozenContract):
    source: NodeRef
    operation: OperationRef
    outcome: str = Field(min_length=1)
    target: NodeRef


__all__ = [
    "CompiledTransition",
    "DeepLinkPolicy",
    "DirtyStatePolicy",
    "NavigationPolicy",
    "NodeKind",
    "NodeRef",
    "RecoveryPolicy",
    "Route",
    "Transition",
]
