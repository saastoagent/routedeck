from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _FrozenContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AgentPolicyRef(_FrozenContract):
    id: str = Field(min_length=1)


class AgentPolicy(_FrozenContract):
    """Trusted model guidance declared by RouteDeck or one product feature."""

    id: str = Field(min_length=1)
    instruction: str = Field(min_length=1)

    @property
    def ref(self) -> AgentPolicyRef:
        return AgentPolicyRef(id=self.id)


__all__ = ["AgentPolicyRef", "AgentPolicy"]
