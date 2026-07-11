from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from .projection import FrozenJsonObject


class _FrozenContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SafetyClass(StrEnum):
    NAVIGATION = "navigation"
    STATE_SELECTION = "state_selection"
    DRAFT = "draft"
    READ_EXTERNAL = "read_external"
    WRITE_EXTERNAL = "write_external"
    DESTRUCTIVE = "destructive"
    CREDENTIAL = "credential"
    ADMIN = "admin"


class ReviewPolicy(StrEnum):
    NONE = "none"
    REQUIRED = "required"


class OperationRef(_FrozenContract):
    id: str = Field(min_length=1)


class ProviderRef(_FrozenContract):
    id: str = Field(min_length=1)


class GuardRef(_FrozenContract):
    id: str = Field(min_length=1)


class ContextProviderSpec(_FrozenContract):
    id: str = Field(min_length=1)
    description: str
    output_schema: FrozenJsonObject = Field(
        default_factory=lambda: FrozenJsonObject({})
    )

    def output_schema_value(self) -> dict[str, object]:
        return self.output_schema.to_dict()

    @property
    def ref(self) -> ProviderRef:
        return ProviderRef(id=self.id)


class EntityProviderSpec(_FrozenContract):
    id: str = Field(min_length=1)
    entity_kind: str = Field(min_length=1)
    description: str
    output_schema: FrozenJsonObject = Field(
        default_factory=lambda: FrozenJsonObject({})
    )

    def output_schema_value(self) -> dict[str, object]:
        return self.output_schema.to_dict()

    @property
    def ref(self) -> ProviderRef:
        return ProviderRef(id=self.id)


class GuardSpec(_FrozenContract):
    id: str = Field(min_length=1)
    description: str

    @property
    def ref(self) -> GuardRef:
        return GuardRef(id=self.id)


class OperationSpec(_FrozenContract):
    id: str = Field(min_length=1)
    title: str
    description: str
    input_schema: FrozenJsonObject = Field(default_factory=lambda: FrozenJsonObject({}))
    safety_class: SafetyClass
    review_policy: ReviewPolicy = ReviewPolicy.NONE
    outcomes: tuple[str, ...]
    provider_refs: tuple[ProviderRef, ...] = ()
    guard_refs: tuple[GuardRef, ...] = ()
    public_metadata: FrozenJsonObject = Field(
        default_factory=lambda: FrozenJsonObject({})
    )

    def input_schema_value(self) -> dict[str, object]:
        return self.input_schema.to_dict()

    def public_metadata_value(self) -> dict[str, object]:
        return self.public_metadata.to_dict()

    @property
    def ref(self) -> OperationRef:
        return OperationRef(id=self.id)


ProviderSpec = ContextProviderSpec | EntityProviderSpec


__all__ = [
    "ContextProviderSpec",
    "EntityProviderSpec",
    "GuardRef",
    "GuardSpec",
    "OperationRef",
    "OperationSpec",
    "ProviderRef",
    "ProviderSpec",
    "ReviewPolicy",
    "SafetyClass",
]
