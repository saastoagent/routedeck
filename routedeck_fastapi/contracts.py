from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from routedeck_core.contracts.failures import FailureKind
from routedeck_core.navigation.transactions import NavigationIntent


class RouteDeckRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DispatchRequest(RouteDeckRequestModel):
    request_id: str = Field(min_length=1)
    expected_session_version: int = Field(ge=0)
    operation_id: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


class ChatStreamRequest(RouteDeckRequestModel):
    request_id: str = Field(min_length=1, max_length=256)
    expected_session_version: int = Field(ge=0)
    message: str = Field(min_length=1, max_length=16_000)

    @field_validator("request_id", "message")
    @classmethod
    def _not_whitespace(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must contain non-whitespace text")
        return value


class AssistantTurnRequest(RouteDeckRequestModel):
    request_id: str = Field(min_length=1, max_length=256)
    expected_session_version: int = Field(ge=0)


class SessionCreateRequest(RouteDeckRequestModel):
    request_id: str = Field(min_length=1)


class ReviewRequest(RouteDeckRequestModel):
    request_id: str = Field(min_length=1)
    expected_session_version: int = Field(ge=0)


class PrivateFormWriteRequest(RouteDeckRequestModel):
    request_id: str = Field(min_length=1)
    expected_session_version: int = Field(ge=0)
    value: dict[str, Any]
    complete: bool = True


class NavigationRequestBody(RouteDeckRequestModel):
    request_id: str = Field(min_length=1)
    expected_session_version: int = Field(ge=0)
    intent: NavigationIntent


@dataclass(frozen=True)
class RouteDeckHttpProblem(Exception):
    status_code: int
    code: str
    public_message: str
    kind: FailureKind = FailureKind.CONTRACT
    phase: str = "http_transport"


__all__ = [
    "AssistantTurnRequest",
    "ChatStreamRequest",
    "DispatchRequest",
    "NavigationRequestBody",
    "PrivateFormWriteRequest",
    "ReviewRequest",
    "RouteDeckHttpProblem",
    "RouteDeckRequestModel",
    "SessionCreateRequest",
]
