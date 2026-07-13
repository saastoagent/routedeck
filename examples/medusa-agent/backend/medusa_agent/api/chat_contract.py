from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from routedeck_fastapi import RouteDeckDependencies


class _ChatRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChatStreamRequest(_ChatRequestModel):
    request_id: str = Field(min_length=1, max_length=256)
    expected_session_version: int = Field(ge=0)
    message: str = Field(min_length=1, max_length=16_000)

    @field_validator("request_id", "message")
    @classmethod
    def _not_whitespace(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must contain non-whitespace text")
        return value


class AgentEventStream(Protocol):
    def astream_events(
        self,
        input: Mapping[str, Any],
        config: Mapping[str, Any] | None = None,
        *,
        version: str = "v2",
        **kwargs: Any,
    ) -> AsyncIterator[Mapping[str, Any]]: ...


@dataclass(frozen=True)
class MedusaChatDependencies:
    routedeck: RouteDeckDependencies
    agent: AgentEventStream

    def __post_init__(self) -> None:
        if not callable(getattr(self.agent, "astream_events", None)):
            raise TypeError("Medusa chat agent must expose astream_events")


ChatDependencyProvider = Callable[
    [Request],
    MedusaChatDependencies | Awaitable[MedusaChatDependencies],
]


__all__ = [
    "AgentEventStream",
    "ChatDependencyProvider",
    "ChatStreamRequest",
    "MedusaChatDependencies",
]
