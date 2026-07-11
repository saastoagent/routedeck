from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from .operations import OperationRef


class _FrozenContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SurfaceLifecycle(StrEnum):
    EPHEMERAL = "ephemeral"
    STABLE = "stable"


class SurfaceRef(_FrozenContract):
    id: str = Field(min_length=1)


class SurfaceAffordanceSpec(_FrozenContract):
    id: str = Field(min_length=1)
    event: str = Field(min_length=1)
    operation: OperationRef | None = None


class SurfaceSpec(_FrozenContract):
    id: str = Field(min_length=1)
    component: str = Field(min_length=1)
    lifecycle: SurfaceLifecycle = SurfaceLifecycle.EPHEMERAL
    affordances: tuple[SurfaceAffordanceSpec, ...] = ()
    public_props_schema: dict[str, JsonValue] = Field(default_factory=dict)

    @property
    def ref(self) -> SurfaceRef:
        return SurfaceRef(id=self.id)


class SurfaceSlotsSpec(_FrozenContract):
    active: SurfaceSpec
    frame: tuple[SurfaceSpec, ...] = ()
    peer: tuple[SurfaceSpec, ...] = ()
    detail: tuple[SurfaceSpec, ...] = ()
    form: tuple[SurfaceSpec, ...] = ()
    review: tuple[SurfaceSpec, ...] = ()
    status: tuple[SurfaceSpec, ...] = ()
    error: tuple[SurfaceSpec, ...] = ()
    diagnostic: tuple[SurfaceSpec, ...] = ()

    def declared_surfaces(self) -> tuple[SurfaceSpec, ...]:
        ordered = (
            self.active,
            *self.frame,
            *self.peer,
            *self.detail,
            *self.form,
            *self.review,
            *self.status,
            *self.error,
            *self.diagnostic,
        )
        surfaces: list[SurfaceSpec] = []
        seen: set[str] = set()
        for surface in ordered:
            if surface.id not in seen:
                surfaces.append(surface)
                seen.add(surface.id)
        return tuple(surfaces)


__all__ = [
    "SurfaceAffordanceSpec",
    "SurfaceLifecycle",
    "SurfaceRef",
    "SurfaceSlotsSpec",
    "SurfaceSpec",
]
