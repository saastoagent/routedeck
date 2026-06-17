from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _parse_sse(text: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for frame in text.strip().split("\n\n"):
        if not frame or frame.startswith(":"):
            continue
        event = None
        data = None
        for line in frame.splitlines():
            if line.startswith("event: "):
                event = line.removeprefix("event: ").strip()
            if line.startswith("data: "):
                data = json.loads(line.removeprefix("data: "))
        if event is not None and data is not None:
            events.append((event, data))
    return events


def _catalog_products():
    from services.medusa_catalog import MedusaCatalogProduct

    return (
        MedusaCatalogProduct(
            handle="t-shirt",
            title="Medusa T-Shirt",
            price="$48.00",
            summary="Premium cotton tee with a relaxed fit.",
            colors=("Natural", "Black", "Navy"),
            sizes=("S", "M", "L"),
            image_url="https://medusa.example/tee.png",
            image_source="medusa_store_api",
        ),
        MedusaCatalogProduct(
            handle="sweatshirt",
            title="Medusa Sweatshirt",
            price="$78.00",
            summary="Soft fleece sweatshirt for everyday comfort.",
            colors=("Olive", "Charcoal", "Black"),
            sizes=("S", "M", "L"),
            image_url="https://medusa.example/sweatshirt.png",
            image_source="medusa_store_api",
        ),
    )


def test_projection_projects_read_only_product_surfaces_and_public_entities() -> None:
    from services.routedeck_projection import build_medusa_projection

    projection = build_medusa_projection(
        path="/detail/t-shirt",
        surface_id="detail.product_detail",
        catalog_products=_catalog_products(),
        catalog_status={"ok": True, "source": "medusa_store_api", "count": 2},
    ).model_dump(mode="json", by_alias=True)

    active_surface = projection["surfaces"]["active"]
    assert active_surface["surface_id"] == "detail.product_detail"
    assert active_surface["component"] == "MedusaProductDetailSurface"
    assert active_surface["surface_kind"] == "embedded"
    assert active_surface["props"]["path"] == "/detail/t-shirt"
    assert active_surface["props"]["surface_id"] == "detail.product_detail"
    assert active_surface["props"]["product"]["handle"] == "t-shirt"
    assert active_surface["props"]["product"]["title"] == "Medusa T-Shirt"
    assert active_surface["props"]["product"]["price"] == "$48.00"
    assert active_surface["props"]["product"]["image_url"] == "https://medusa.example/tee.png"
    assert active_surface["props"]["product"]["image_source"] == "medusa_store_api"
    assert active_surface["props"]["surface_summary"] == "Read-only detail surface for Medusa T-Shirt."

    assert projection["legal_operations"] == []
    assert projection["surface_affordances"] == []
    assert {
        "kind": "product",
        "entity_key": "product:t-shirt",
        "label": "Medusa T-Shirt",
        "parent_label": None,
        "rendered_on": ["browse.product_list", "detail.product_detail"],
        "operations": [],
        "metadata": {"handle": "t-shirt", "price": "$48.00"},
    } in projection["available_entities"]
    assert "prod_" not in str(projection)
    assert "variant_" not in str(projection)
    assert "cart_" not in str(projection)


def test_projection_defines_all_slice_surfaces_and_backend_projected_chat_chips() -> None:
    from services.routedeck_projection import build_medusa_projection

    cases = [
        ("/", None, "home.chat", "MedusaHomeChatSurface", "Show me products"),
        ("/browse", None, "browse.product_list", "MedusaProductListSurface", "Compare visible products"),
        ("/detail/t-shirt", None, "detail.product_detail", "MedusaProductDetailSurface", "Ask about this product"),
        ("/cart", None, "cart.summary", "MedusaCartSummarySurface", "Review my cart"),
    ]

    for path, surface_id, expected_surface_id, expected_component, expected_chip in cases:
        projection = build_medusa_projection(
            path=path,
            surface_id=surface_id,
            catalog_products=_catalog_products(),
            catalog_status={"ok": True, "source": "medusa_store_api", "count": 2},
        ).model_dump(mode="json", by_alias=True)

        assert projection["surfaces"]["active"]["surface_id"] == expected_surface_id
        assert projection["surfaces"]["active"]["component"] == expected_component
        assert projection["surfaces"]["active"]["role"] == "active"
        assert projection["surfaces"]["active"]["surface_kind"] == "embedded"
        assert projection["presentation_state"]["active_surface_id"] == expected_surface_id
        assert expected_chip in [chip["label"] for chip in projection["presentation_state"]["chat_suggestions"]]


def test_projection_without_catalog_does_not_silently_fabricate_products() -> None:
    from services.routedeck_projection import build_medusa_projection

    projection = build_medusa_projection(
        path="/browse",
        surface_id="browse.product_list",
    ).model_dump(mode="json", by_alias=True)

    active_props = projection["surfaces"]["active"]["props"]
    assert active_props["products"] == []
    assert active_props["catalog_status"]["ok"] is False
    assert projection["available_entities"] == []
    assert "Medusa T-Shirt" not in str(projection)
    assert "$48.00" not in str(projection)


def test_planning_context_is_projection_derived_and_safe_for_chat() -> None:
    from services.planning_context import build_planning_context, planning_context_message
    from services.routedeck_projection import build_medusa_projection

    projection = build_medusa_projection(
        path="/detail/t-shirt",
        surface_id="detail.product_detail",
        catalog_products=_catalog_products(),
        catalog_status={"ok": True, "source": "medusa_store_api", "count": 2},
    )
    context = build_planning_context(projection)

    assert context["current"] == {
        "node_id": "detail",
        "surface_id": "detail.product_detail",
        "deeplink": "/detail/t-shirt?surface_id=detail.product_detail",
    }
    assert context["reachable_nodes"] == ["cart"]
    assert context["rendered_surface"]["component"] == "MedusaProductDetailSurface"
    assert context["rendered_surface"]["summary"] == "Read-only detail surface for Medusa T-Shirt."
    assert {"kind": "product", "entity_key": "product:t-shirt", "label": "Medusa T-Shirt"} in context[
        "available_entities"
    ]
    assert context["capabilities"] == ["Shopping orientation"]
    assert "diagnostics" not in context
    assert "prod_" not in str(context)
    assert "variant_" not in str(context)

    message = planning_context_message(context)
    assert "Current RouteDeck planning context" in message
    assert "detail.product_detail" in message
    assert "Medusa T-Shirt" in message
    assert "price=$48.00" in message
    assert "colors=Natural, Black, Navy" in message
    assert "sizes=S, M, L" in message
    assert "orientation-only reachable nodes: cart" in message
    assert "not next-step recommendations or actions" in message


@pytest.mark.asyncio
async def test_chat_stream_injects_projection_planning_context_into_agent_input(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    from langchain_core.messages import AIMessageChunk, HumanMessage, SystemMessage

    from core.config import Settings
    from services import chat_service as chat_service_module
    from services.chat_service import ChatService
    from services.routedeck_projection import build_medusa_projection

    def fake_runtime_projection(*, path: str = "/", surface_id: str | None = None, settings=None):
        return build_medusa_projection(
            path=path,
            surface_id=surface_id,
            catalog_products=_catalog_products(),
            catalog_status={"ok": True, "source": "medusa_store_api", "count": 2},
        )

    monkeypatch.setattr(chat_service_module, "build_runtime_medusa_projection", fake_runtime_projection)

    class FakeGraph:
        def __init__(self) -> None:
            self.input = None

        async def astream_events(self, graph_input, config, version):
            self.input = graph_input
            assert config == {"configurable": {"thread_id": "thread-context"}}
            assert version == "v2"
            yield {"event": "on_chat_model_stream", "data": {"chunk": AIMessageChunk(content="Context aware.")}}

    fake_graph = FakeGraph()
    service = ChatService(settings=Settings(openai_api_key="test-key"), graph=fake_graph)

    events = [
        event
        async for event in service.stream(
            "what am I viewing?",
            conversation_id="thread-context",
            route_context={"path": "/detail/t-shirt", "surface_id": "detail.product_detail"},
        )
    ]

    messages = fake_graph.input["messages"]
    assert len(messages) == 2
    assert isinstance(messages[0], SystemMessage)
    assert "Current RouteDeck planning context" in messages[0].content
    assert "Medusa T-Shirt" in messages[0].content
    assert "detail.product_detail" in messages[0].content
    assert "prod_" not in messages[0].content
    assert isinstance(messages[1], HumanMessage)
    assert messages[1].content == "what am I viewing?"

    parsed = _parse_sse("".join(events))
    assert [event for event, _data in parsed] == [
        "stream_start",
        "agent_start",
        "message_delta",
        "agent_end",
        "stream_end",
    ]
