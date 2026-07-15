from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from ..inspection import event_cursor
from ..responses import exception_response
from ..session_http import authenticated_snapshot, resolve_dependencies
from ..sse import stream_events
from . import DependencyProvider


def create_event_routes(provider: DependencyProvider) -> APIRouter:
    router = APIRouter()

    @router.get("/events")
    async def events(request: Request):
        try:
            dependencies = await resolve_dependencies(provider, request)
            snapshot = await authenticated_snapshot(request, dependencies)
            after_cursor = event_cursor(request)
            first_page = await dependencies.store.events_after(
                snapshot.session_id,
                after_cursor,
                dependencies.sse.replay_batch_size,
            )
            body = stream_events(
                session_id=snapshot.session_id,
                after_cursor=after_cursor,
                store=dependencies.store,
                notifier=dependencies.notifier,
                settings=dependencies.sse,
                initial_page=first_page,
            )
            return StreamingResponse(
                body,
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "private, no-store, no-transform",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        except Exception as error:
            return exception_response(error)

    return router


__all__ = ["create_event_routes"]
