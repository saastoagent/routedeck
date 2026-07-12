from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_serializer,
    model_validator,
)

from .projection import PublicEntityHandle, PublicValue


class _FrozenContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ExactRouteParameter(_FrozenContract):
    """One exact public route binding selected by a successful operation."""

    name: str = Field(min_length=1)
    value: str = Field(min_length=1)


class EntityBindingEffect(_FrozenContract):
    """One public capability paired with its private authoritative identifier."""

    public: PublicEntityHandle
    private_id: SecretStr = Field(min_length=1)
    allowed_operation_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _unique_operations(self) -> EntityBindingEffect:
        if len(self.allowed_operation_ids) != len(set(self.allowed_operation_ids)):
            raise ValueError("effect operation IDs must be unique")
        if any(not operation_id for operation_id in self.allowed_operation_ids):
            raise ValueError("effect operation IDs must be non-empty")
        return self

    @field_serializer("private_id", when_used="json")
    def _serialize_private_id(self, value: SecretStr) -> str:
        # The durable execution journal must replay the exact private binding.
        # Public results, projections, and events never serialize SessionEffects.
        return value.get_secret_value()


class EntityKindEffects(_FrozenContract):
    """Replace every binding of one entity kind with this authoritative set."""

    entity_kind: str = Field(min_length=1)
    bindings: tuple[EntityBindingEffect, ...] = ()

    @model_validator(mode="after")
    def _matching_unique_entities(self) -> EntityKindEffects:
        handles = tuple(binding.public.handle for binding in self.bindings)
        if len(handles) != len(set(handles)):
            raise ValueError("effect entity handles must be unique")
        if any(
            binding.public.entity_kind != self.entity_kind for binding in self.bindings
        ):
            raise ValueError("effect entity kinds must match their replacement set")
        return self


class PublicSurfaceEffect(_FrozenContract):
    """Replace the public props for one declared target-node surface."""

    surface_id: str = Field(min_length=1)
    values: tuple[PublicValue, ...] = ()

    @model_validator(mode="after")
    def _unique_values(self) -> PublicSurfaceEffect:
        names = tuple(value.name for value in self.values)
        if len(names) != len(set(names)):
            raise ValueError("effect surface value names must be unique")
        return self


class SessionEffects(_FrozenContract):
    """Serializable canonical state effects from one successful operation.

    Entity sets replace by kind, surface updates replace by surface ID, and a
    supplied route-parameter tuple is the exact target location binding.
    Private-form removals explicitly purge completed sensitive workflows.
    Session completion is durable retention metadata: it does not enter the
    public projection, and stores apply it atomically with the successful
    operation commit that carries this effect in its execution journal.
    """

    replace_entities: tuple[EntityKindEffects, ...] = ()
    surface_updates: tuple[PublicSurfaceEffect, ...] = ()
    remove_private_form_ids: tuple[str, ...] = ()
    route_params: tuple[ExactRouteParameter, ...] | None = None
    complete_session: bool = False

    @model_validator(mode="after")
    def _unique_replacement_keys(self) -> SessionEffects:
        kinds = tuple(effect.entity_kind for effect in self.replace_entities)
        if len(kinds) != len(set(kinds)):
            raise ValueError("effect entity replacement kinds must be unique")
        surfaces = tuple(effect.surface_id for effect in self.surface_updates)
        if len(surfaces) != len(set(surfaces)):
            raise ValueError("effect surface IDs must be unique")
        if len(self.remove_private_form_ids) != len(set(self.remove_private_form_ids)):
            raise ValueError("effect private form IDs must be unique")
        if any(not form_id for form_id in self.remove_private_form_ids):
            raise ValueError("effect private form IDs must be non-empty")
        if self.route_params is not None:
            names = tuple(parameter.name for parameter in self.route_params)
            if len(names) != len(set(names)):
                raise ValueError("effect route parameter names must be unique")
        handles = tuple(
            binding.public.handle
            for effect in self.replace_entities
            for binding in effect.bindings
        )
        if len(handles) != len(set(handles)):
            raise ValueError("effect public handles must be globally unique")
        return self

    @property
    def is_empty(self) -> bool:
        return (
            not self.replace_entities
            and not self.surface_updates
            and not self.remove_private_form_ids
            and self.route_params is None
            and not self.complete_session
        )


__all__ = [
    "EntityBindingEffect",
    "EntityKindEffects",
    "ExactRouteParameter",
    "PublicSurfaceEffect",
    "SessionEffects",
]
