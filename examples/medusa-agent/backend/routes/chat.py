from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.chat_service import chat_service


router = APIRouter(tags=["medusa-agent-chat"])


class ChatStreamRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    session_id: str | None = None


@router.post("/api/medusa-agent/agent/stream")
async def stream_agent(body: ChatStreamRequest) -> StreamingResponse:
    async def generate():
        async for event in chat_service.stream(
            message=body.message,
            conversation_id=body.conversation_id,
            session_id=body.session_id,
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
