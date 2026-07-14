from __future__ import annotations

from collections.abc import Iterator, Mapping
from enum import StrEnum
from math import isfinite
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_core import core_schema

from .failures import RouteDeckFailure
from .interactions import RouteDeckInteractionState


JsonScalar = str | int | float | bool | None


class FrozenJson:
    """Recursively immutable JSON with ordinary JSON serialization."""

    __slots__ = ("_value",)
    _value: object

    def __init__(self, value: Any) -> None:
        object.__setattr__(self, "_value", self._freeze(value))

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("FrozenJson is immutable")

    @classmethod
    def _freeze(cls, value: Any) -> object:
        if isinstance(value, FrozenJson):
            return value._value
        if value is None or isinstance(value, (str, int, bool)):
            return value
        if isinstance(value, float):
            if not isfinite(value):
                raise TypeError("JSON numbers must be finite")
            return value
        if isinstance(value, Mapping):
            keys = tuple(value)
            if any(not isinstance(key, str) for key in keys):
                raise TypeError("JSON object keys must be strings")
            items: list[tuple[str, object]] = []
            for key in sorted(keys):
                items.append((key, cls._freeze(value[key])))
            return ("object", tuple(items))
        if isinstance(value, (list, tuple)):
            return ("array", tuple(cls._freeze(item) for item in value))
        raise TypeError(f"Value is not JSON-compatible: {type(value).__name__}")

    @classmethod
    def _thaw(cls, value: object) -> Any:
        if isinstance(value, tuple) and len(value) == 2 and value[0] == "object":
            return {key: cls._thaw(item) for key, item in value[1]}
        if isinstance(value, tuple) and len(value) == 2 and value[0] == "array":
            return [cls._thaw(item) for item in value[1]]
        return value

    def to_python(self) -> Any:
        return self._thaw(self._value)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, FrozenJson) and self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value)

    def __repr__(self) -> str:
        return f"FrozenJson({self.to_python()!r})"

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: object,
        handler: object,
    ) -> core_schema.CoreSchema:
        del source_type, handler
        return core_schema.no_info_plain_validator_function(
            cls._validate,
            json_schema_input_schema=core_schema.any_schema(),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda value: value.to_python(),
                when_used="always",
            ),
        )

    @classmethod
    def _validate(cls, value: object) -> FrozenJson:
        return value if isinstance(value, cls) else cls(value)


class FrozenJsonObject(FrozenJson, Mapping[str, Any]):
    """Recursively immutable JSON constrained to an object at the root."""

    __slots__ = ()

    def __init__(self, value: Any) -> None:
        super().__init__(value)
        if not isinstance(self.to_python(), dict):
            raise TypeError("Value must be a JSON object")

    def to_dict(self) -> dict[str, Any]:
        value = self.to_python()
        if not isinstance(value, dict):
            raise TypeError("Value is not a JSON object")
        return value

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.to_dict())

    def __len__(self) -> int:
        return len(self.to_dict())


class _FrozenContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=True,
    )


class DataClassification(StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"
    SENSITIVE = "sensitive"


class ClassifiedValue(_FrozenContract):
    name: str = Field(min_length=1)
    value: FrozenJson
    classification: DataClassification


class PublicValue(_FrozenContract):
    name: str = Field(min_length=1)
    value: FrozenJson


class PublicEntityHandle(_FrozenContract):
    entity_kind: str = Field(min_length=1)
    handle: str = Field(min_length=1)
    values: tuple[PublicValue, ...] = ()

    @model_validator(mode="after")
    def _unique_values(self) -> PublicEntityHandle:
        names = tuple(value.name for value in self.values)
        if len(names) != len(set(names)):
            raise ValueError("public entity value names must be unique")
        return self


class ProjectedOperation(_FrozenContract):
    operation_id: str = Field(min_length=1)
    title: str
    safety_class: str
    review_required: bool = False


class ProjectedSuggestedAction(_FrozenContract):
    action_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    arguments: FrozenJsonObject = Field(
        default_factory=lambda: FrozenJsonObject({})
    )


class ProjectedSurface(_FrozenContract):
    surface_id: str = Field(min_length=1)
    component: str = Field(min_length=1)
    props: tuple[PublicValue, ...] = ()


class ProjectedSurfaceSlots(_FrozenContract):
    active: ProjectedSurface | None
    frame: tuple[ProjectedSurface, ...] = ()
    peer: tuple[ProjectedSurface, ...] = ()
    detail: tuple[ProjectedSurface, ...] = ()
    form: tuple[ProjectedSurface, ...] = ()
    review: tuple[ProjectedSurface, ...] = ()
    status: tuple[ProjectedSurface, ...] = ()
    error: tuple[ProjectedSurface, ...] = ()
    diagnostic: tuple[ProjectedSurface, ...] = ()

    def __getitem__(
        self,
        slot: str,
    ) -> ProjectedSurface | tuple[ProjectedSurface, ...] | None:
        if slot not in self.__class__.model_fields:
            raise KeyError(slot)
        return getattr(self, slot)


class ProjectionLocation(_FrozenContract):
    node_id: str = Field(min_length=1)
    route_params: tuple[PublicValue, ...] = ()


class ProjectedNavigation(_FrozenContract):
    current: ProjectionLocation
    current_entry_id: int = Field(ge=1)
    route_template: str
    resume_handle: str | None
    can_back: bool
    can_forward: bool
    can_cancel: bool
    back_node_id: str | None = None
    forward_node_id: str | None = None
    cancel_target_node_id: str | None = None


class ProjectionStatus(_FrozenContract):
    code: str = "ready"
    message: str | None = None


class ProjectionDiagnostics(_FrozenContract):
    schema_version: int = Field(ge=1)
    navgraph_version: str = Field(min_length=1)
    current_node_id: str = Field(min_length=1)
    declared_provider_ids: tuple[str, ...] = ()


class PublicProjection(_FrozenContract):
    session_version: int = Field(ge=0)
    projection_version: int = Field(ge=0)
    event_cursor: int = Field(ge=0)
    current: ProjectionLocation
    interaction: RouteDeckInteractionState
    navigation: ProjectedNavigation
    legal_operations: tuple[ProjectedOperation, ...]
    suggested_actions: tuple[ProjectedSuggestedAction, ...]
    entities: tuple[PublicEntityHandle, ...]
    surfaces: ProjectedSurfaceSlots
    status: ProjectionStatus
    failure: RouteDeckFailure | None = None
    diagnostics: ProjectionDiagnostics

    @property
    def legal_operation_ids(self) -> tuple[str, ...]:
        return tuple(operation.operation_id for operation in self.legal_operations)


__all__ = [
    "ClassifiedValue",
    "DataClassification",
    "FrozenJson",
    "FrozenJsonObject",
    "ProjectedNavigation",
    "ProjectedOperation",
    "ProjectedSuggestedAction",
    "ProjectedSurface",
    "ProjectedSurfaceSlots",
    "ProjectionDiagnostics",
    "ProjectionLocation",
    "ProjectionStatus",
    "PublicEntityHandle",
    "PublicProjection",
    "PublicValue",
]
