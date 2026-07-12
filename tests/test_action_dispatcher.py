from __future__ import annotations

import asyncio

import pytest

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


def test_action_dispatcher_rejects_default_handlers():
    async def default_handler(action_id, state, payload, context):
        return RouteDeckActionResult(
            state={**state, "node": context["targets"][action_id]},
            messages=[],
            evidence=[],
        )

    with pytest.raises(TypeError, match="default_handler"):
        RouteDeckActionDispatcher(default_handler=default_handler)


def test_action_dispatcher_fails_loudly_for_an_unregistered_action():
    dispatcher = RouteDeckActionDispatcher()

    with pytest.raises(KeyError, match="demo.missing"):
        asyncio.run(
            dispatcher.dispatch(
                "demo.missing",
                state={"node": "home"},
                payload={},
                context={},
            )
        )
