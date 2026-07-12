from __future__ import annotations

from typing import Protocol, runtime_checkable

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from routedeck_fastapi import RouteDeckDependencies


router = APIRouter(prefix="/api/medusa-agent", tags=["medusa-agent"])


@runtime_checkable
class MedusaAgentReadinessProbe(Protocol):
    """Read-only dependency checks owned by the product runtime."""

    async def routedeck_store_ready(self) -> bool: ...

    async def medusa_ready(self) -> bool: ...


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", response_model=None)
async def ready(request: Request) -> JSONResponse:
    routedeck = getattr(request.app.state, "routedeck_dependencies", None)
    agent = getattr(request.app.state, "medusa_chat_agent", None)
    readiness = getattr(request.app.state, "medusa_readiness", None)
    if (
        not isinstance(routedeck, RouteDeckDependencies)
        or not callable(getattr(agent, "astream_events", None))
        or not isinstance(readiness, MedusaAgentReadinessProbe)
    ):
        return _readiness_response(ready=False)

    routedeck_store_ready = await readiness.routedeck_store_ready()
    medusa_ready = await readiness.medusa_ready()
    if not isinstance(routedeck_store_ready, bool) or not isinstance(
        medusa_ready, bool
    ):
        raise TypeError("Medusa readiness checks must return bool")
    return _readiness_response(ready=routedeck_store_ready and medusa_ready)


def _readiness_response(*, ready: bool) -> JSONResponse:
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ready" if ready else "not_ready"},
        headers={"Cache-Control": "no-store"},
    )


__all__ = ["MedusaAgentReadinessProbe", "router"]
