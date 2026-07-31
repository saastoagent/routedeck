from __future__ import annotations

import hashlib
import json
from collections import defaultdict, deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from time import perf_counter
from typing import Any

from langchain.agents.middleware import ModelRequest, ModelResponse
from langchain_core.messages import BaseMessage
from langchain_core.tools import BaseTool

from .tool_wrapper import RouteDeckInvocationContext


_SENSITIVE_KEYS = ("authorization", "api_key", "apikey", "password", "secret")
_SENSITIVE_TOKEN_KEYS = frozenset({
    "token", "access_token", "refresh_token", "bearer_token",
    "verification_token", "reset_token",
})


@dataclass
class RouteDeckInvocationTraceRecorder:
    """Bounded, sanitized evidence of RouteDeck-to-model invocations."""

    retention_per_session: int = 20
    _traces: dict[str, deque[dict[str, Any]]] = field(
        default_factory=lambda: defaultdict(deque), init=False
    )
    _lock: Lock = field(default_factory=Lock, init=False)

    def __post_init__(self) -> None:
        if self.retention_per_session < 1:
            raise ValueError("invocation trace retention must be positive")

    def start(
        self,
        session_id: str,
        request: ModelRequest[RouteDeckInvocationContext],
        model_context: Any,
    ) -> tuple[dict[str, Any], float]:
        boundary_request = _sanitize({
            "messages": [_message_payload(item) for item in request.messages],
            "system_message": (
                _message_payload(request.system_message)
                if request.system_message is not None else None
            ),
            "tools": [_tool_payload(tool) for tool in request.tools],
            "tool_choice": request.tool_choice,
            "response_format": request.response_format,
            "model_settings": request.model_settings,
            "model": _model_identity(request.model),
        })
        context_payload = _sanitize(
            model_context.model_dump(mode="json")
            if hasattr(model_context, "model_dump") else model_context
        )
        trace = {
            "kind": "model_invocation",
            "started_at": datetime.now(UTC).isoformat(),
            "status": "running",
            "route_deck_context": _stage(context_payload),
            "model_boundary_request": _stage(boundary_request),
            "provider_serialization": {
                "status": "unavailable",
                "reason": "No provider transport hook is installed; this is not raw provider HTTP.",
            },
            "provider_result": {"status": "pending"},
        }
        with self._lock:
            bucket = self._traces[session_id]
            bucket.append(trace)
            while len(bucket) > self.retention_per_session:
                bucket.popleft()
        return trace, perf_counter()

    def complete(
        self, trace: dict[str, Any], started: float, response: ModelResponse[Any]
    ) -> None:
        messages = [_message_payload(item) for item in response.result]
        trace.update(status="completed", duration_ms=round((perf_counter() - started) * 1000, 2))
        trace["provider_result"] = _stage(_sanitize({
            "messages": messages,
            "structured_response": response.structured_response,
            "metadata": [_response_metadata(item) for item in response.result],
        }))

    def fail(self, trace: dict[str, Any], started: float, error: Exception) -> None:
        trace.update(status="failed", duration_ms=round((perf_counter() - started) * 1000, 2))
        trace["provider_result"] = {
            "status": "failed",
            "error_type": type(error).__name__,
            "message": str(error)[:500],
        }

    def inspect(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            traces = [dict(item) for item in self._traces.get(session_id, ())]
        return {
            "kind": "invocation_trace_history",
            "retention_per_session": self.retention_per_session,
            "capture_limits": {"max_depth": 20, "max_string_chars": 100000, "max_collection_items": 500},
            "traces": list(reversed(traces)),
        }


def _stage(value: Any) -> dict[str, Any]:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return {"status": "captured", "sha256": hashlib.sha256(encoded.encode()).hexdigest(), "value": value}


def _message_payload(message: BaseMessage) -> dict[str, Any]:
    payload = message.model_dump(mode="json", exclude_none=True)
    payload.pop("id", None)
    return _sanitize(payload)


def _response_metadata(message: BaseMessage) -> dict[str, Any]:
    return _sanitize({
        "response_metadata": getattr(message, "response_metadata", {}),
        "usage_metadata": getattr(message, "usage_metadata", None),
    })


def _model_identity(model: Any) -> dict[str, Any]:
    return {"type": f"{type(model).__module__}.{type(model).__qualname__}"}


def _tool_payload(tool: Any) -> Any:
    if isinstance(tool, BaseTool):
        return {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.get_input_schema().model_json_schema(),
        }
    return tool


def _sanitize(value: Any, depth: int = 0) -> Any:
    if depth >= 20:
        return "[truncated]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:100000] + ("...[truncated]" if len(value) > 100000 else "")
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= 500:
                result["[truncated]"] = "collection limit reached"
                break
            name = str(key)
            lowered = name.lower()
            sensitive = (
                any(part in lowered for part in _SENSITIVE_KEYS)
                or lowered in _SENSITIVE_TOKEN_KEYS
            )
            result[name] = "[redacted]" if sensitive else _sanitize(item, depth + 1)
        return result
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [_sanitize(item, depth + 1) for item in list(value)[:500]]
    if hasattr(value, "model_dump"):
        return _sanitize(
            value.model_dump(mode="json", warnings=False, fallback=str), depth + 1
        )
    return str(value)[:1000]


__all__ = ["RouteDeckInvocationTraceRecorder"]
