from __future__ import annotations

from typing import Any

from fastapi import Request

from routedeck_core.contracts.projection import PublicProjection
from routedeck_core.contracts.session import SessionSnapshot
from routedeck_core.ports import RouteDeckAgentContextInspector

from .contracts import RouteDeckHttpProblem
from .dependencies import RouteDeckDependencies


def event_cursor(request: Request) -> int:
    after_values = request.query_params.getlist("after")
    if len(after_values) > 1:
        raise RouteDeckHttpProblem(
            400,
            "conflicting_event_cursor",
            "The event cursor is invalid.",
        )
    header_value = request.headers.get("last-event-id")
    after = parse_cursor(after_values[0], "after") if after_values else None
    header = (
        parse_cursor(header_value, "Last-Event-ID")
        if header_value is not None
        else None
    )
    if after is not None and header is not None and after != header:
        raise RouteDeckHttpProblem(
            400,
            "conflicting_event_cursor",
            "Last-Event-ID and after must match.",
        )
    return header if header is not None else (after if after is not None else 0)


def parse_cursor(value: str, field_name: str) -> int:
    try:
        cursor = int(value)
    except (TypeError, ValueError) as error:
        raise RouteDeckHttpProblem(
            400,
            "invalid_event_cursor",
            f"{field_name} must be a non-negative integer.",
        ) from error
    if cursor < 0 or str(cursor) != value.strip():
        raise RouteDeckHttpProblem(
            400,
            "invalid_event_cursor",
            f"{field_name} must be a non-negative integer.",
        )
    return cursor


def inspection(
    dependencies: RouteDeckDependencies,
    snapshot: SessionSnapshot,
    projection: PublicProjection,
) -> dict[str, Any]:
    current_node_id = projection.current.node_id
    node = next(
        node for node in dependencies.app.graph.nodes if node.id == current_node_id
    )
    legal_ids = set(projection.legal_operation_ids)
    reachable = sorted(
        {
            transition.target.id
            for transition in dependencies.app.graph.transitions
            if transition.source.id == current_node_id
        }
    )
    route_traces = [
        {
            "source": transition.source.id,
            "operation_id": transition.operation.id,
            "outcome": transition.outcome,
            "target": transition.target.id,
        }
        for transition in dependencies.app.graph.transitions
        if transition.source.id == current_node_id
    ]
    agent_context = (
        dependencies.agent_driver.inspect_agent_context(snapshot)
        if isinstance(dependencies.agent_driver, RouteDeckAgentContextInspector)
        else None
    )
    return {
        "current_node": current_node_id,
        "reachable_nodes": reachable,
        "legal_operations": [
            operation.model_dump(mode="json")
            for operation in projection.legal_operations
        ],
        "blocked_operations": [
            {
                "operation_id": operation.id,
                "reason": "not_legal_in_current_state",
            }
            for operation in node.operations
            if operation.id not in legal_ids
        ],
        "guard_explanations": [guard.id for guard in node.guards],
        "capabilities": [
            capability.model_dump(mode="json") for capability in node.capabilities
        ],
        "surfaces": projection.surfaces.model_dump(mode="json"),
        "route_traces": route_traces,
        "diagnostics": {
            **projection.diagnostics.model_dump(mode="json"),
            "session_version": snapshot.session_version,
            "projection_version": snapshot.projection_version,
            "event_cursor": snapshot.event_cursor,
        },
        "agent_context": agent_context,
    }


__all__ = ["event_cursor", "inspection", "parse_cursor"]
