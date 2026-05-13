from __future__ import annotations

import asyncio
from typing import Any, TypedDict

from routedeck_core import (
    RouteDeckActionSpec,
    RouteDeckEdgeSpec,
    RouteDeckManifest,
    RouteDeckNodeSpec,
    build_runtime_snapshot,
)
from routedeck_langgraph import (
    assert_route_transition,
    build_route_deck_state_graph,
    validate_langgraph_contract,
)


class DemoState(TypedDict, total=False):
    node: str
    active_stage_id: str
    route_group: str
    selected_action_id: str | None
    message: str
    transition: dict[str, Any]


MANIFEST = RouteDeckManifest(
    version="minimal_langgraph_v1",
    nodes=[
        RouteDeckNodeSpec(
            id="intent",
            label="Intent",
            lane="system",
            description="Choose what to do next.",
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


def confirmed(_edge: RouteDeckEdgeSpec, state: dict[str, Any]) -> bool:
    return state.get("node") == "done"


CONDITION_RESOLVERS = {"confirmed": confirmed}
GROUPS = {"public": {"intent"}, "terminal": {"done"}}


async def intent_node(state: DemoState) -> dict[str, Any]:
    if state.get("selected_action_id") == "intent.confirm":
        return {"node": "done", "message": "Confirmed."}
    return {"message": "Choose Confirm to continue."}


async def done_node(_state: DemoState) -> dict[str, Any]:
    return {"message": "Done."}


def finalize_node(state: DemoState) -> dict[str, Any]:
    from_node = state.get("active_stage_id") or "intent"
    to_node = state.get("node") or from_node
    transition = assert_route_transition(
        MANIFEST,
        from_node=from_node,
        to_node=to_node,
        state=state,
        condition_resolvers=CONDITION_RESOLVERS,
    )
    return {"transition": transition.model_dump()}


async def main() -> None:
    handlers = {"intent": intent_node, "done": done_node}
    errors = validate_langgraph_contract(
        MANIFEST,
        handlers,
        CONDITION_RESOLVERS,
        groups=GROUPS,
    )
    if errors:
        raise SystemExit("\n".join(errors))

    graph = build_route_deck_state_graph(
        manifest=MANIFEST,
        state_schema=DemoState,
        handlers=handlers,
        condition_resolvers=CONDITION_RESOLVERS,
        groups=GROUPS,
        finalize_node=finalize_node,
    ).compile()

    result = await graph.ainvoke({"node": "intent", "selected_action_id": "intent.confirm"})
    snapshot = build_runtime_snapshot(
        MANIFEST,
        current_node=result["node"],
        valid_actions=[],
        blocked_actions=[],
        executed_nodes=[result["active_stage_id"], result["node"]],
        diagnostics={"transition": result["transition"]},
    )
    print(snapshot)


if __name__ == "__main__":
    asyncio.run(main())
