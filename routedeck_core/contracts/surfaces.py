from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from jsonschema.exceptions import SchemaError
from jsonschema.validators import validator_for
from pydantic import BaseModel, ConfigDict, Field
from pydantic import model_validator

from .operations import OperationRef
from .projection import FrozenJsonObject


_COMMON_PUBLIC_SCHEMA_KEYWORDS = frozenset(
    {"type", "title", "description", "enum", "const"}
)
_PUBLIC_SCHEMA_KEYWORDS_BY_TYPE: dict[str, frozenset[str]] = {
    "object": frozenset(
        {
            "properties",
            "required",
            "additionalProperties",
            "minProperties",
            "maxProperties",
        }
    ),
    "array": frozenset({"items", "minItems", "maxItems", "uniqueItems"}),
    "string": frozenset({"minLength", "maxLength", "format"}),
    "number": frozenset(
        {
            "minimum",
            "maximum",
            "exclusiveMinimum",
            "exclusiveMaximum",
            "multipleOf",
        }
    ),
    "integer": frozenset(
        {
            "minimum",
            "maximum",
            "exclusiveMinimum",
            "exclusiveMaximum",
            "multipleOf",
        }
    ),
    "boolean": frozenset(),
    "null": frozenset(),
}


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
    public_props_schema: FrozenJsonObject = Field(
        default_factory=lambda: FrozenJsonObject({})
    )

    @model_validator(mode="after")
    def _validate_public_props_schema(self) -> SurfaceSpec:
        schema = self.public_props_schema.to_dict()
        if not schema:
            return self
        try:
            validator_for(schema).check_schema(schema)
        except SchemaError as exc:
            raise ValueError("public_props_schema must be valid JSON Schema") from exc
        _require_default_deny_schema(schema, root=True)
        return self

    def public_props_schema_value(self) -> dict[str, object]:
        return self.public_props_schema.to_dict()

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


def _require_default_deny_schema(
    schema: Mapping[str, object],
    *,
    root: bool = False,
) -> None:
    schema_type = schema.get("type")
    if not isinstance(schema_type, str):
        raise ValueError("public schemas must declare one explicit type")
    if root and schema_type != "object":
        raise ValueError("public_props_schema root type must be object")
    type_keywords = _PUBLIC_SCHEMA_KEYWORDS_BY_TYPE.get(schema_type)
    if type_keywords is None:
        raise ValueError("public schemas must use a supported explicit type")
    unsupported_keywords = set(schema).difference(
        _COMMON_PUBLIC_SCHEMA_KEYWORDS,
        type_keywords,
    )
    if unsupported_keywords:
        raise ValueError("public schemas must use explicit structural declarations")
    if schema_type == "object":
        if not isinstance(schema.get("properties"), Mapping):
            raise ValueError("public object schemas must declare a properties mapping")
        if schema.get("additionalProperties") is not False:
            raise ValueError(
                "public object schemas must set additionalProperties to false"
            )
        properties = schema["properties"]
        if not isinstance(properties, Mapping):
            raise ValueError("public object properties must be a mapping")
        for property_schema in properties.values():
            if not isinstance(property_schema, Mapping):
                raise ValueError("public property schemas must be objects")
            _require_default_deny_schema(property_schema)
    elif schema_type == "array":
        items = schema.get("items")
        if not isinstance(items, Mapping):
            raise ValueError("public array schemas must declare one items schema")
        _require_default_deny_schema(items)


__all__ = [
    "SurfaceAffordanceSpec",
    "SurfaceLifecycle",
    "SurfaceRef",
    "SurfaceSlotsSpec",
    "SurfaceSpec",
]
