from __future__ import annotations

from core.config import Settings
from services.planning_context import build_medusa_planning_context
from services.routedeck_provider import get_routedeck_runtime
from services.routedeck_runtime import MedusaRouteDeckRuntime


async def build_routedeck_system_prompt(
    settings: Settings,
    session_id: str = "default",
    runtime: MedusaRouteDeckRuntime | None = None,
) -> str:
    runtime = runtime or get_routedeck_runtime(settings=settings)
    projection = await runtime.projection(context={"probe_timeout": 0.5, "session_id": session_id})
    return build_medusa_planning_context(projection)
