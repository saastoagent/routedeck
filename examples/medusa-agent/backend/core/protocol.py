from __future__ import annotations

import json
from typing import Any


def encode_sse(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def stream_start(conversation_id: str, model: str) -> str:
    return encode_sse(
        "stream_start",
        {"conversation_id": conversation_id, "model": model},
    )


def agent_start(agent_name: str = "medusa-commerce-agent") -> str:
    return encode_sse("agent_start", {"agent_name": agent_name})


def message_delta(content: str) -> str:
    return encode_sse("message_delta", {"content": content})


def projection_update(data: dict[str, object]) -> str:
    return encode_sse("projection_update", data)


def agent_end() -> str:
    return encode_sse("agent_end", {})


def stream_end() -> str:
    return encode_sse("stream_end", {})


def error(message: str, code: str = "internal_error") -> str:
    return encode_sse("error", {"message": message, "code": code})


def keepalive() -> str:
    return ": ping\n\n"


def chunk_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    return ""
