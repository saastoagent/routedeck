from __future__ import annotations

from .models import RouteDeckManifest


class RouteDeckValidationError(ValueError):
    pass


def _matches_pattern(pattern: str, value: str) -> bool:
    return value.startswith(pattern[:-1]) if pattern.endswith("*") else value == pattern


def validate_manifest(
    manifest: RouteDeckManifest,
    *,
    masked_payload_keys: list[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    node_ids = {node.id for node in manifest.nodes}
    action_ids = {action.id for action in manifest.actions}
    masked_keys = set(masked_payload_keys or [])

    for edge in manifest.edges:
        if edge.from_stage not in node_ids:
            errors.append(f"Edge from unknown node: {edge.from_stage}")
        if edge.to_stage not in node_ids:
            errors.append(f"Edge to unknown node: {edge.to_stage}")
        if edge.action_id and edge.action_id not in action_ids:
            errors.append(f"Edge references unknown action: {edge.action_id}")

    for node in manifest.nodes:
        if node.lane != "terminal" and not node.allowed_actions and not node.expected_input:
            errors.append(f"Node has no visible action or expected input: {node.id}")
        for action_id in node.allowed_actions:
            if action_id not in action_ids:
                errors.append(f"Node {node.id} references unknown action: {action_id}")

    for action in manifest.actions:
        for node_id in action.allowed_nodes:
            if not any(_matches_pattern(node_id, candidate) for candidate in node_ids):
                errors.append(f"Action {action.id} references unknown node: {node_id}")
        for field in action.fields:
            if field.sensitive and masked_keys and field.key not in masked_keys:
                errors.append(f"Sensitive field {field.key} is not covered by masked payload policy")

    return errors
