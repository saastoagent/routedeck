from __future__ import annotations

from core.config import Settings
from services.routedeck_runtime import MedusaRouteDeckRuntime


async def build_routedeck_system_prompt(settings: Settings, session_id: str = "default") -> str:
    runtime = MedusaRouteDeckRuntime(settings=settings)
    projection = await runtime.projection(context={"probe_timeout": 0.5, "session_id": session_id})
    setup = projection.surfaces.get("active").props.get("setup", {}) if "active" in projection.surfaces else {}
    legal_operation_labels = [operation.label for operation in projection.legal_operations]
    legal_operations = ", ".join(legal_operation_labels) if legal_operation_labels else "none"
    setup_ready = bool(setup.get("ready"))

    return "\n".join(
        [
            "RouteDeck runtime context:",
            f"- current graph node: {projection.graph_node}",
            f"- active surface: {projection.surfaces.get('active').variant if 'active' in projection.surfaces else 'none'}",
            f"- setup ready: {str(setup_ready).lower()}",
            f"- legal RouteDeck operations: {legal_operations}",
            "- dispatch execution: unavailable when there are no legal operations",
            "",
            "Use this RouteDeck context as the source of truth for available app capabilities.",
            "When legal RouteDeck operations exist, you may describe only what those operations make possible.",
            "When there are no legal RouteDeck operations, do not claim to execute product, catalog, or commerce actions.",
            "If setup is not ready, explain in product language that local demo Medusa is not connected for that capability yet.",
            "Do not invent catalog items, prices, variants, inventory, or availability that are not provided by RouteDeck context.",
            "Do not expose RouteDeck operation ids, graph nodes, diagnostics, dispatch traces, or endpoint paths to the shopper.",
        ]
    )
