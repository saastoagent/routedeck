from __future__ import annotations

from typing import Any

from .models import RouteDeckManifest


def reachable_nodes(manifest: RouteDeckManifest, node_id: str | None) -> list[str]:
    if not node_id:
        return []
    return [edge.to_stage for edge in manifest.edges if edge.from_stage == node_id]


def build_runtime_snapshot(
    manifest: RouteDeckManifest,
    *,
    current_node: str | None,
    valid_actions: list[dict[str, Any]] | None = None,
    blocked_actions: list[dict[str, str]] | None = None,
    executed_nodes: list[str] | None = None,
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    node_ids = [node.id for node in manifest.nodes]
    node = next((candidate for candidate in manifest.nodes if candidate.id == current_node), None)
    return {
        "current_node": current_node,
        "reachable_nodes": reachable_nodes(manifest, current_node),
        "valid_actions": valid_actions or [],
        "blocked_actions": blocked_actions or [],
        "executed_nodes": executed_nodes or [],
        "progress": {
            "node_index": node_ids.index(current_node) if current_node in node_ids else None,
            "node_count": len(node_ids),
        },
        "recovery_prompts": [node.recovery_prompt] if node and node.recovery_prompt else [],
        "diagnostics": diagnostics or {},
    }
