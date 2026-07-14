from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .projection import FrozenJsonObject


class _FrozenContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=True,
    )


class SuggestedActionVisibilitySpec(_FrozenContract):
    """Declarative session-state requirements for projecting one action."""

    required_entity_kinds: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _unique_entity_kinds(self) -> SuggestedActionVisibilitySpec:
        if len(self.required_entity_kinds) != len(set(self.required_entity_kinds)):
            raise ValueError("required entity kinds must be unique")
        if any(not entity_kind for entity_kind in self.required_entity_kinds):
            raise ValueError("required entity kinds cannot be empty")
        return self


class SuggestedActionSpec(_FrozenContract):
    """One compact, RouteDeck-supervised operation invitation."""

    id: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    label: str | None = Field(default=None, min_length=1)
    arguments: FrozenJsonObject = Field(
        default_factory=lambda: FrozenJsonObject({})
    )
    visibility: SuggestedActionVisibilitySpec = Field(
        default_factory=SuggestedActionVisibilitySpec
    )

    def arguments_value(self) -> dict[str, object]:
        return self.arguments.to_dict()


__all__ = ["SuggestedActionSpec", "SuggestedActionVisibilitySpec"]
