from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FailureKind(StrEnum):
    CONTRACT = "contract"
    STATE_CONFLICT = "state_conflict"
    CONTEXT_PROVIDER = "context_provider"
    GUARD = "guard"
    REVIEW = "review"
    TRANSPORT = "transport"
    PROVIDER_PROTOCOL = "provider_protocol"
    BUSINESS = "business"
    PERSISTENCE = "persistence"
    EXTERNAL_OUTCOME_UNKNOWN = "external_outcome_unknown"
    INTERNAL = "internal"


class FailureSafeDetails(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    affected_capability: str | None = None
    provider: str | None = None
    provider_code: str | None = None
    http_status: int | None = Field(default=None, ge=100, le=599)
    delivery_phase: Literal["not_sent", "possibly_sent", "response_received"] | None = None


class RouteDeckFailure(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: FailureKind
    code: str
    phase: str
    correlation_id: str
    operation_id: str | None = None
    request_id: str | None = None
    public_message: str
    recovery_directive: str | None = None
    safe_details: FailureSafeDetails = Field(default_factory=FailureSafeDetails)


__all__ = ["FailureKind", "FailureSafeDetails", "RouteDeckFailure"]
