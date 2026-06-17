from __future__ import annotations

from fastapi import APIRouter

from services.routedeck_projection import build_runtime_medusa_projection


router = APIRouter(tags=["medusa-agent-projection"])


@router.get("/api/medusa-agent/projection")
async def projection(path: str = "/", surface_id: str | None = None) -> dict:
    return build_runtime_medusa_projection(path=path, surface_id=surface_id).model_dump(
        mode="json",
        by_alias=True,
    )
