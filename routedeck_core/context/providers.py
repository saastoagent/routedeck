from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ..contracts.projection import PublicEntityHandle


class OperationContextScope(BaseModel):
    """Default-deny context declaration for one legal operation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    node_id: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    provider_ids: tuple[str, ...] = ()
    entities: tuple[PublicEntityHandle, ...] = ()


__all__ = ["OperationContextScope"]
