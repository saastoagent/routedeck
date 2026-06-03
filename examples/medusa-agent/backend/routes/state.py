from __future__ import annotations

from fastapi import APIRouter

from core.config import Settings
from services.medusa_setup import probe_medusa_setup


router = APIRouter(tags=["medusa-agent-state"])


@router.get("/api/medusa-agent/state")
async def state():
    return await probe_medusa_setup(Settings.from_env())
