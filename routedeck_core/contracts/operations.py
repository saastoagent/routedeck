from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, JsonValue


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
    output_schema: dict[str, Any] = Field(default_factory=dict)

    @property
    def ref(self) -> ProviderRef:
        return ProviderRef(id=self.id)


class EntityProviderSpec(_FrozenContract):
    id: str = Field(min_length=1)
    entity_kind: str = Field(min_length=1)
    description: str
    output_schema: dict[str, Any] = Field(default_factory=dict)

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
    input_schema: dict[str, Any] = Field(default_factory=dict)
    safety_class: SafetyClass
    review_policy: ReviewPolicy = ReviewPolicy.NONE
    outcomes: tuple[str, ...]
    provider_refs: tuple[ProviderRef, ...] = ()
    guard_refs: tuple[GuardRef, ...] = ()
    public_metadata: dict[str, JsonValue] = Field(default_factory=dict)

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
