from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class _OpaqueCapability(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    capability: SecretStr
    fencing_token: int = Field(ge=1)


class TurnOwnerKind(StrEnum):
    CHAT = "chat"
    SURFACE = "surface"
    REVIEW = "review"
    SYSTEM = "system"


class TurnClaim(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    session_id: str = Field(min_length=1)
    expected_session_version: int = Field(ge=0)
    request_id: str = Field(min_length=1)
    request_fingerprint: str = Field(min_length=1)
    owner_kind: TurnOwnerKind
    parent_turn_id: str | None = None


class TurnLease(_OpaqueCapability):
    session_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)


class ExecutionClaim(_OpaqueCapability):
    session_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    attempt_id: str = Field(min_length=1)


class StoreWriteCapability(_OpaqueCapability):
    session_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)


__all__ = [
    "ExecutionClaim",
    "StoreWriteCapability",
    "TurnClaim",
    "TurnLease",
    "TurnOwnerKind",
]
