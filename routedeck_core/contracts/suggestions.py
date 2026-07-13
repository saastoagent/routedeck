from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .projection import FrozenJsonObject


class _FrozenContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=True,
    )


class SuggestedActionSpec(_FrozenContract):
    """One compact, RouteDeck-supervised operation invitation."""

    id: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    label: str | None = Field(default=None, min_length=1)
    arguments: FrozenJsonObject = Field(
        default_factory=lambda: FrozenJsonObject({})
    )

    def arguments_value(self) -> dict[str, object]:
        return self.arguments.to_dict()


__all__ = ["SuggestedActionSpec"]
