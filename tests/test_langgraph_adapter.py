from __future__ import annotations

import sys
import asyncio
import subprocess
from typing import Any, TypedDict

from routedeck_core import RouteDeckActionSpec, RouteDeckEdgeSpec, RouteDeckManifest, RouteDeckNodeSpec
from routedeck_langgraph import (
    assert_route_transition,
    build_route_deck_state_graph,
    validate_langgraph_contract,
)


class AdapterState(TypedDict, total=False):
    node: str
    active_stage_id: str
    route_group: str
    visited: bool


def _manifest() -> RouteDeckManifest:
    return RouteDeckManifest(
        version="test",
        nodes=[
            RouteDeckNodeSpec(
                id="intent",
                label="Intent",
                lane="system",
                description="Collect intent.",
                allowed_actions=["intent.confirm"],
            ),
            RouteDeckNodeSpec(
                id="done",
                label="Done",
                lane="terminal",
                description="Terminal state.",
            ),
        ],
        edges=[
            RouteDeckEdgeSpec(
                from_stage="intent",
                to_stage="done",
                type="conditional",
                condition="confirmed",
                action_id="intent.confirm",
            )
        ],
        actions=[
            RouteDeckActionSpec(
                id="intent.confirm",
                label="Confirm",
                allowed_nodes=["intent"],
            )
        ],
    )


def _resolver(_edge, state: dict[str, Any]) -> bool:
    return state.get("node") == "done"


def test_routedeck_core_does_not_import_langgraph():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import routedeck_core; raise SystemExit(1 if 'langgraph' in sys.modules else 0)",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_adapter_validation_reports_missing_handler_and_resolver():
    manifest = _manifest()

    errors = validate_langgraph_contract(
        manifest,
        handlers={"intent": lambda state: state},
        condition_resolvers={},
        groups={"main": {"intent"}},
    )

    assert "RouteDeck node has no LangGraph handler: done" in errors
    assert "RouteDeck edge condition has no LangGraph resolver: confirmed" in errors
    assert "RouteDeck node is missing from LangGraph groups: done" in errors


def test_adapter_transition_diagnostics_and_invalid_transition():
    manifest = _manifest()
    diagnostics = assert_route_transition(
        manifest,
        from_node="intent",
        to_node="done",
        state={"node": "done"},
        condition_resolvers={"confirmed": _resolver},
    )

    assert diagnostics.model_dump() == {
        "from_stage": "intent",
        "to_stage": "done",
        "condition": "confirmed",
        "edge_type": "conditional",
        "action_id": "intent.confirm",
        "source": "route_deck",
    }

    try:
        assert_route_transition(
            manifest,
            from_node="done",
            to_node="intent",
            state={"node": "intent"},
            condition_resolvers={"confirmed": _resolver},
        )
    except ValueError as exc:
        assert "not executable" in str(exc)
    else:
        raise AssertionError("Expected invalid transition to fail.")


def test_adapter_builds_grouped_state_graph():
    manifest = _manifest()

    async def intent_node(_state: AdapterState) -> dict[str, Any]:
        return {"node": "done", "visited": True}

    async def done_node(_state: AdapterState) -> dict[str, Any]:
        return {"visited": True}

    graph = build_route_deck_state_graph(
        manifest=manifest,
        state_schema=AdapterState,
        handlers={"intent": intent_node, "done": done_node},
        condition_resolvers={"confirmed": _resolver},
        groups={"public": {"intent"}, "terminal": {"done"}},
    ).compile()

    result = asyncio.run(graph.ainvoke({"node": "intent"}))

    assert result["node"] == "done"
    assert result["visited"] is True
    assert result["active_stage_id"] == "intent"
    assert result["route_group"] == "public"
