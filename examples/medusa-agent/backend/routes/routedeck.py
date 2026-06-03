from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from routedeck_core import RouteDeckDispatchInput

from services.routedeck_manifest import SLICE3_MANIFEST
from services.routedeck_runtime import MedusaRouteDeckRuntime


router = APIRouter(tags=["routedeck"])
runtime = MedusaRouteDeckRuntime()


@router.get("/api/routedeck/manifest")
async def manifest():
    return SLICE3_MANIFEST.model_dump(mode="json", by_alias=True)


@router.get("/api/routedeck/snapshot")
async def snapshot(session_id: str = "default"):
    return (await runtime.snapshot({"session_id": session_id})).model_dump(mode="json")


@router.get("/api/routedeck/projection")
async def projection(session_id: str = "default"):
    return (await runtime.projection({"session_id": session_id})).model_dump(mode="json")


@router.post("/api/routedeck/dispatch")
async def dispatch(body: RouteDeckDispatchInput):
    context = {"session_id": "default", **body.context}
    request = body.model_copy(update={"context": context})
    try:
        return (await runtime.dispatch(request, context=context)).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/routedeck/inspect")
async def inspect(body: dict | None = None, session_id: str = "default"):
    return {"introspection": (await runtime.inspect(body or {}, context={"session_id": session_id})).model_dump(mode="json")}


@router.get("/api/routedeck/stream")
async def stream(session_id: str = "default"):
    async def generate():
        async for event in runtime.stream({"session_id": session_id}):
            payload = json.dumps(event.model_dump(mode="json"))
            yield f"event: {event.event_type}\ndata: {payload}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
