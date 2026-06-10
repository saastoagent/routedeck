from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.chat_service import chat_service


router = APIRouter(tags=["medusa-agent-chat"])


class ChatStreamRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    route_context: dict[str, Any] | None = None


@router.post("/api/medusa-agent/agent/stream")
async def stream_agent(body: ChatStreamRequest) -> StreamingResponse:
    async def generate():
        async for event in chat_service.stream(
            message=body.message,
            conversation_id=body.conversation_id,
            route_context=body.route_context,
        ):
            yield event

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/medusa-agent/debug/context-thread")
async def debug_context_thread(conversation_id: str | None = None) -> dict[str, Any]:
    return chat_service.debug_context_thread(conversation_id)
