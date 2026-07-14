from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator


class RouteDeckInteractionPhase(StrEnum):
    IDLE = "idle"
    ACTIVE = "active"


class RouteDeckInteractionOwnerType(StrEnum):
    CHAT = "chat"
    SURFACE = "surface"
    REVIEW = "review"
    SYSTEM = "system"
    NAVIGATION = "navigation"


class RouteDeckInteractionState(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    phase: RouteDeckInteractionPhase = RouteDeckInteractionPhase.IDLE
    owner: RouteDeckInteractionOwnerType | None = None

    @model_validator(mode="after")
    def _phase_matches_owner(self) -> RouteDeckInteractionState:
        if self.phase is RouteDeckInteractionPhase.IDLE and self.owner is not None:
            raise ValueError("idle interaction state cannot have an owner")
        if self.phase is RouteDeckInteractionPhase.ACTIVE and self.owner is None:
            raise ValueError("active interaction state requires an owner")
        return self

    @classmethod
    def active(
        cls,
        owner: RouteDeckInteractionOwnerType,
    ) -> RouteDeckInteractionState:
        return cls(phase=RouteDeckInteractionPhase.ACTIVE, owner=owner)


__all__ = [
    "RouteDeckInteractionOwnerType",
    "RouteDeckInteractionPhase",
    "RouteDeckInteractionState",
]
