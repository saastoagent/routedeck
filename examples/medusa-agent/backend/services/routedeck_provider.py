from __future__ import annotations

from core.config import Settings
from services.routedeck_runtime import MedusaRouteDeckRuntime


_runtime: MedusaRouteDeckRuntime | None = None


def get_routedeck_runtime(settings: Settings | None = None) -> MedusaRouteDeckRuntime:
    global _runtime
    if _runtime is None:
        _runtime = MedusaRouteDeckRuntime(settings=settings)
    return _runtime


def set_routedeck_runtime(runtime: MedusaRouteDeckRuntime | None) -> None:
    global _runtime
    _runtime = runtime
