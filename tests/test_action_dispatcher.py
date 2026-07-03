from __future__ import annotations

import asyncio

from routedeck_core import RouteDeckActionDispatcher, RouteDeckActionResult


def test_action_dispatcher_runs_registered_async_handler():
    async def handler(state, payload, context):
        return RouteDeckActionResult(
            state={**state, "node": payload["node"]},
            messages=[context["message"]],
            evidence=[{"type": "handled"}],
        )

    dispatcher = RouteDeckActionDispatcher({"demo.open": handler})

    result = asyncio.run(
        dispatcher.dispatch(
            "demo.open",
            state={"node": "home"},
            payload={"node": "details"},
            context={"message": "opened"},
        )
    )

    assert dispatcher.has_handler("demo.open") is True
    assert result.state == {"node": "details"}
    assert result.messages == ["opened"]
    assert result.evidence == [{"type": "handled"}]


def test_action_dispatcher_uses_default_handler_for_unregistered_actions():
    async def default_handler(action_id, state, payload, context):
        return RouteDeckActionResult(
            state={**state, "node": context["targets"][action_id]},
            messages=[],
            evidence=[],
        )

    dispatcher = RouteDeckActionDispatcher(default_handler=default_handler)

    result = asyncio.run(
        dispatcher.dispatch(
            "demo.default",
            state={"node": "home"},
            payload={},
            context={"targets": {"demo.default": "fallback"}},
        )
    )

    assert dispatcher.has_handler("demo.default") is False
    assert result.state == {"node": "fallback"}
