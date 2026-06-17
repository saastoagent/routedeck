from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from core.protocol import projection_update
from services.route_events import route_event_bus


router = APIRouter(tags=["medusa-agent-routedeck-stream"])


@router.get("/api/medusa-agent/route-stream")
async def route_stream(conversation_id: str, replay_only: bool = False) -> StreamingResponse:
    async def generate():
        if replay_only:
            for event in route_event_bus.recent(conversation_id):
                yield projection_update(event)
            return

        async for event in route_event_bus.stream(conversation_id):
            yield projection_update(event)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
