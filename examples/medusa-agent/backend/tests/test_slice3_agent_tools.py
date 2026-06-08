from __future__ import annotations

import sys
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
ROUTEDECK_ROOT = BACKEND_ROOT.parents[2]
for path in (BACKEND_ROOT, ROUTEDECK_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


@pytest.mark.asyncio
async def test_routedeck_prompt_names_capabilities_without_operation_ids(monkeypatch: pytest.MonkeyPatch):
    from routedeck_core import RouteDeckCapabilitySpec, RouteDeckLocation, RouteDeckNavigationState, RouteDeckOperation, RouteDeckProjection

    from core.config import Settings
    from services import routedeck_prompt

    projection = RouteDeckProjection(
        current_context="browse",
        graph_node="browse",
        legal_operations=[
            RouteDeckOperation(id="catalog.list", label="Browse products", safety_class="read_external"),
            RouteDeckOperation(id="cart.add_item", label="Add selected item to cart", safety_class="write_external"),
        ],
        capabilities=[
            RouteDeckCapabilitySpec(capability_id="catalog.browse", label="Browse catalog", operation_ids=["catalog.list"]),
            RouteDeckCapabilitySpec(capability_id="cart.manage", label="Manage demo cart", operation_ids=["cart.add_item"]),
        ],
        surfaces={},
        navigation=RouteDeckNavigationState(current=RouteDeckLocation(node_id="browse")),
    )

    class FakeRuntime:
        async def projection(self, context=None):
            assert context == {"probe_timeout": 0.5, "session_id": "s1"}
            return projection

    monkeypatch.setattr(routedeck_prompt, "get_routedeck_runtime", lambda settings=None: FakeRuntime())

    prompt = await routedeck_prompt.build_routedeck_system_prompt(Settings(openai_api_key="test-key"), session_id="s1")

    assert prompt.startswith("Medusa planning context:")
    assert "Browse catalog" in prompt
    assert "Manage demo cart" in prompt
    assert "catalog.list" not in prompt
    assert "cart.add_item" not in prompt


@pytest.mark.asyncio
async def test_agent_tool_calls_routedeck_dispatch():
    from routedeck_core import (
        RouteDeckDispatchResult,
        RouteDeckEvent,
        RouteDeckLocation,
        RouteDeckNavigationState,
        RouteDeckProjection,
        RouteDeckRuntimeState,
        RouteDeckSurface,
    )

    from services.agent_tools import build_agent_tools

    calls = []
    projection = RouteDeckProjection(
        current_context="browse",
        graph_node="browse",
        surfaces={
            "active": RouteDeckSurface(
                name="active",
                component="MedusaProductList",
                variant="product_list",
                role="active",
                props={"products": []},
            )
        },
        navigation=RouteDeckNavigationState(current=RouteDeckLocation(node_id="browse")),
    )

    class FakeRuntime:
        async def dispatch(self, request, context=None):
            calls.append((request.operation_id, request.args, context))
            state = RouteDeckRuntimeState(projection=projection, status="idle")
            return RouteDeckDispatchResult(
                operation_id=request.operation_id,
                accepted=True,
                state=state,
                active_surface=projection.surfaces["active"],
                messages=[{"content": "Products are ready to browse."}],
                events=[
                    RouteDeckEvent(
                        event_type="operation_completed",
                        projection_version=projection.projection_version,
                        payload={"state": state.model_dump(mode="json")},
                    )
                ],
            )

    captured_events = []
    tools = build_agent_tools(runtime=FakeRuntime(), session_id="s1", event_sink=captured_events.append)
    browse_tool = next(tool for tool in tools if tool.name == "browse_products")

    result = await browse_tool.ainvoke({})

    assert calls == [("catalog.list", {}, {"session_id": "s1", "source": "agent_tool"})]
    assert "Products are ready" in result
    assert "Medusa T-Shirt" not in result
    assert "catalog.list" not in result
    assert captured_events == [
        RouteDeckEvent(
            event_type="operation_completed",
            projection_version=projection.projection_version,
            payload={"state": RouteDeckRuntimeState(projection=projection, status="idle").model_dump(mode="json")},
        )
    ]


@pytest.mark.asyncio
async def test_browse_tool_summarizes_product_surface_without_private_ids():
    from routedeck_core import (
        RouteDeckDispatchResult,
        RouteDeckLocation,
        RouteDeckNavigationState,
        RouteDeckProjection,
        RouteDeckRuntimeState,
        RouteDeckSurface,
    )

    from services.agent_tools import build_agent_tools

    projection = RouteDeckProjection(
        current_context="browse",
        graph_node="browse",
        surfaces={
            "active": RouteDeckSurface(
                name="active",
                component="MedusaProductList",
                variant="product_list",
                role="active",
                props={
                    "products": [
                        {
                            "entity_key": "product:entity_public",
                            "title": "Medusa T-Shirt",
                            "variants": [{"entity_key": "variant:entity_public", "title": "S / Black"}],
                        },
                        {"entity_key": "product:entity_other", "title": "Medusa Sweatshirt", "variants": []},
                    ]
                },
            )
        },
        navigation=RouteDeckNavigationState(current=RouteDeckLocation(node_id="browse")),
    )

    class FakeRuntime:
        async def dispatch(self, request, context=None):
            return RouteDeckDispatchResult(
                operation_id=request.operation_id,
                accepted=True,
                state=RouteDeckRuntimeState(projection=projection, status="idle"),
                active_surface=projection.surfaces["active"],
                messages=[{"content": "Products are ready to browse."}],
            )

    tools = build_agent_tools(runtime=FakeRuntime(), session_id="s1")
    browse_tool = next(tool for tool in tools if tool.name == "browse_products")

    result = await browse_tool.ainvoke({})

    assert "Medusa T-Shirt" in result
    assert "Medusa Sweatshirt" in result
    assert "entity_public" not in result
    assert "catalog.list" not in result


@pytest.mark.asyncio
async def test_add_item_tool_passes_variant_and_quantity_to_dispatch():
    from routedeck_core import (
        RouteDeckDispatchResult,
        RouteDeckLocation,
        RouteDeckNavigationState,
        RouteDeckProjection,
        RouteDeckRuntimeState,
    )

    from services.agent_tools import build_agent_tools

    calls = []
    projection = RouteDeckProjection(
        current_context="cart",
        graph_node="cart",
        surfaces={},
        navigation=RouteDeckNavigationState(current=RouteDeckLocation(node_id="cart")),
    )

    class FakeRuntime:
        async def dispatch(self, request, context=None):
            calls.append((request.operation_id, request.args, context))
            return RouteDeckDispatchResult(
                operation_id=request.operation_id,
                accepted=True,
                state=RouteDeckRuntimeState(projection=projection, status="idle"),
                messages=[{"content": "Added to cart."}],
            )

    tools = build_agent_tools(runtime=FakeRuntime(), session_id="s1")
    add_tool = next(tool for tool in tools if tool.name == "add_selected_variant_to_cart")

    result = await add_tool.ainvoke({"entity_key": "variant:entity_public", "quantity": 2})

    assert calls == [
        (
            "cart.add_item",
            {"entity_key": "variant:entity_public", "quantity": 2},
            {"session_id": "s1", "source": "agent_tool"},
        )
    ]
    assert result == "Added to cart."
