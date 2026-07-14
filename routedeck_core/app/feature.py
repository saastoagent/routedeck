from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ..contracts.agent import AgentPolicyRef, AgentPolicySpec
from ..contracts.application import NodeSpec
from ..contracts.navigation import NodeRef, TransitionSpec


class _FrozenContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FeatureSpec(_FrozenContract):
    namespace: str = Field(min_length=1)
    nodes: tuple[NodeSpec, ...]
    transitions: tuple[TransitionSpec, ...] = ()
    agent_policies: tuple[AgentPolicySpec, ...] = ()
    policy_refs: tuple[AgentPolicyRef, ...] = ()


class ApplicationSpec(_FrozenContract):
    name: str = Field(min_length=1)
    entry_node: NodeRef
    features: tuple[FeatureSpec, ...]
    transitions: tuple[TransitionSpec, ...] = ()

__all__ = ["ApplicationSpec", "FeatureSpec"]
