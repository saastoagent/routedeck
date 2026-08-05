from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RouteDeckInteractionPhase(StrEnum):
    IDLE = "idle"
    ACTIVE = "active"


class RouteDeckInteractionOwnerType(StrEnum):
    CHAT = "chat"
    SURFACE = "surface"
    REVIEW = "review"
    SYSTEM = "system"
    NAVIGATION = "navigation"


class OperationSource(StrEnum):
    SURFACE = "surface"
    AGENT = "agent"
    SYSTEM = "system"
    ROUTE = "route"


class RouteDeckInteractionState(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    phase: RouteDeckInteractionPhase = RouteDeckInteractionPhase.IDLE
    owner: RouteDeckInteractionOwnerType | None = None
    request_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _phase_matches_owner(self) -> RouteDeckInteractionState:
        if self.phase is RouteDeckInteractionPhase.IDLE and (
            self.owner is not None or self.request_id is not None
        ):
            raise ValueError("idle interaction state cannot have an owner or request")
        if self.phase is RouteDeckInteractionPhase.ACTIVE and (
            self.owner is None or self.request_id is None
        ):
            raise ValueError("active interaction state requires an owner and request")
        return self

    @classmethod
    def active(
        cls,
        owner: RouteDeckInteractionOwnerType,
        request_id: str,
    ) -> RouteDeckInteractionState:
        return cls(
            phase=RouteDeckInteractionPhase.ACTIVE,
            owner=owner,
            request_id=request_id,
        )


__all__ = [
    "OperationSource",
    "RouteDeckInteractionOwnerType",
    "RouteDeckInteractionPhase",
    "RouteDeckInteractionState",
]
