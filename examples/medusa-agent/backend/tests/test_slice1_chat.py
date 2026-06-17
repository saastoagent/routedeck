from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.route_events import route_event_bus


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


def _assistant_text(events: list[tuple[str, dict]]) -> str:
    return "".join(data["content"] for event, data in events if event == "message_delta")


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


def _fixture_projection(*, path: str = "/", surface_id: str | None = None, settings=None):
    from services.routedeck_projection import build_medusa_projection

    return build_medusa_projection(
        path=path,
        surface_id=surface_id,
        catalog_products=_catalog_products(),
        catalog_status={"ok": True, "source": "medusa_store_api", "count": 2},
    )


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    from core import config as config_module

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("MEDUSA_AGENT_MODEL", raising=False)
    monkeypatch.setattr(config_module, "DEFAULT_ENV_PATH", tmp_path / "missing.env")
    monkeypatch.chdir(tmp_path)

    from app import app
    from services import chat_service as chat_service_module

    chat_service_module.chat_service.settings = config_module.Settings.from_env()
    chat_service_module.chat_service.graph = None
    route_event_bus.clear()

    return TestClient(app)


def test_stream_endpoint_returns_true_sse_with_required_events(client: TestClient):
    response = client.post(
        "/api/medusa-agent/agent/stream",
        json={"message": "hi", "conversation_id": "contract-chat"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse(response.text)
    assert [event for event, _data in events] == [
        "stream_start",
        "agent_start",
        "error",
        "agent_end",
        "stream_end",
    ]
    assert events[0][1]["conversation_id"] == "contract-chat"
    assert events[0][1]["model"] == "gpt-5-mini"
    assert "fallback" not in events[0][1]
    assert events[1][1]["agent_name"] == "medusa-commerce-agent"
    assert events[2][1]["code"] == "openai_api_key_missing"


def test_missing_api_key_does_not_emit_simulated_assistant_text(client: TestClient):
    response = client.post("/api/medusa-agent/agent/stream", json={"message": "show me products"})

    assert response.status_code == 200
    events = _parse_sse(response.text)
    assert "message_delta" not in [event for event, _data in events]
    assert _assistant_text(events) == ""
    assert events[2][1]["message"] == "OPENAI_API_KEY is required for the Medusa agent."


def test_backend_route_surface_is_chat_only(client: TestClient):
    assert client.get("/api/medusa-agent/health").status_code == 200
    assert client.post(
        "/api/medusa-agent/agent/stream",
        json={"message": "hi", "conversation_id": "chat-boundary"},
    ).status_code == 200

    forbidden_routes = [
        ("GET", "/api/medusa-agent/state"),
        ("GET", "/api/medusa-agent/route-manifest"),
        ("GET", "/api/medusa-agent/route-snapshot"),
        ("POST", "/api/medusa-agent/action"),
        ("POST", "/api/medusa-agent/inspect"),
        ("GET", "/api/routedeck/anything"),
        ("POST", "/api/routedeck/anything"),
    ]

    for method, path in forbidden_routes:
        response = client.request(method, path, json={} if method == "POST" else None)
        assert response.status_code == 404, f"{method} {path} must not exist in Slice 1"


def test_route_stream_replays_routedeck_projection_events_without_assistant_text(client: TestClient):
    projection = _fixture_projection(
        path="/browse",
        surface_id="browse.product_list",
    ).model_dump(mode="json", by_alias=True)

    route_event_bus.publish(
        "route-stream-contract",
        {
            "event_type": "projection_update",
            "source": "test",
            "accepted_intent": "browse_products",
            "route_context": {"path": "/browse", "surface_id": "browse.product_list"},
            "projection_version": 2,
            "projection": projection,
        },
    )

    with client.stream(
        "GET",
        "/api/medusa-agent/route-stream",
        params={"conversation_id": "route-stream-contract", "replay_only": "true"},
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        first_chunk = next(response.iter_text())

    assert "event: projection_update" in first_chunk
    events = _parse_sse(first_chunk)
    assert len(events) == 1
    event_name, data = events[0]
    assert event_name == "projection_update"
    assert data["event_type"] == "projection_update"
    assert data["source"] == "test"
    assert data["accepted_intent"] == "browse_products"
    assert data["route_context"] == {"path": "/browse", "surface_id": "browse.product_list"}
    assert data["projection_version"] == 2
    assert data["projection"]["graph_node"] == "browse"
    assert data["projection"]["presentation_state"]["active_surface_id"] == "browse.product_list"
    assert data["projection"]["navigation"]["current"]["surface_id"] == "browse.product_list"
    assert len(data["projection"]["navgraph"]["nodes"]) == 4
    assert len(data["projection"]["navgraph"]["edges"]) == 3
    assert "message_delta" not in first_chunk


@pytest.mark.asyncio
async def test_route_event_bus_delivers_live_projection_events_after_subscription():
    route_event_bus.clear()
    event = {
        "event_type": "projection_update",
        "source": "test",
        "accepted_intent": "browse_products",
        "route_context": {"path": "/browse", "surface_id": "browse.product_list"},
    }
    stream = route_event_bus.stream("live-route-stream-contract")
    next_event = asyncio.create_task(stream.__anext__())

    await asyncio.sleep(0)
    route_event_bus.publish("live-route-stream-contract", event)

    try:
        assert await asyncio.wait_for(next_event, timeout=1) == event
    finally:
        await stream.aclose()


@pytest.mark.asyncio
async def test_graph_path_maps_conversation_id_to_thread_id_and_streams_model_deltas(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    from langchain_core.messages import AIMessageChunk, HumanMessage

    from core.config import Settings
    from services.chat_service import ChatService

    class FakeGraph:
        def __init__(self) -> None:
            self.config = None
            self.input = None

        async def astream_events(self, graph_input, config, version):
            self.config = config
            self.input = graph_input
            assert version == "v2"
            yield {"event": "on_chat_model_stream", "data": {"chunk": AIMessageChunk(content="Hello ")}}
            yield {"event": "on_chat_model_stream", "data": {"chunk": AIMessageChunk(content="there.")}}

    fake_graph = FakeGraph()
    settings = Settings(openai_api_key="test-key")
    service = ChatService(settings=settings, graph=fake_graph)

    events = [event async for event in service.stream("hi", conversation_id="thread-123")]

    assert fake_graph.config == {"configurable": {"thread_id": "thread-123"}}
    assert len(fake_graph.input["messages"]) == 1
    assert isinstance(fake_graph.input["messages"][0], HumanMessage)
    assert fake_graph.input["messages"][0].content == "hi"
    parsed = _parse_sse("".join(events))
    assert [event for event, _data in parsed].count("message_delta") == 2
    assert "routedeck_event" not in [event for event, _data in parsed]
    assert _assistant_text(parsed) == "Hello there."
    assert "fallback" not in parsed[0][1]


@pytest.mark.asyncio
async def test_graph_path_ignores_non_model_events_without_route_deck_frames(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    from langchain_core.messages import AIMessageChunk

    from core.config import Settings
    from services.chat_service import ChatService
    from services import agent_tools as agent_tools_module
    from services.agent_tools import open_medusa_surface

    monkeypatch.setattr(agent_tools_module, "build_runtime_medusa_projection", _fixture_projection)

    class FakeGraph:
        async def astream_events(self, _graph_input, config, version):
            assert config == {"configurable": {"thread_id": "thread-route"}}
            assert version == "v2"
            yield {"event": "on_tool_start", "data": {"name": "ignored"}}
            yield {
                "event": "on_tool_end",
                "data": {"output": open_medusa_surface.invoke({"surface_id": "browse.product_list"})},
            }
            yield {"event": "on_chat_model_stream", "data": {"chunk": AIMessageChunk(content="Products ready.")}}

    service = ChatService(settings=Settings(openai_api_key="test-key"), graph=FakeGraph())
    route_event_bus.clear()

    parsed = _parse_sse("".join([event async for event in service.stream("show products", conversation_id="thread-route")]))

    assert [event for event, _data in parsed] == [
        "stream_start",
        "agent_start",
        "message_delta",
        "agent_end",
        "stream_end",
    ]
    projection_events = route_event_bus.recent("thread-route")
    assert len(projection_events) == 1
    projection_update = projection_events[0]
    assert projection_update["event_type"] == "projection_update"
    assert projection_update["source"] == "medusa_agent_tool"
    assert projection_update["accepted_intent"] == "browse_products"
    assert projection_update["route_context"] == {
        "path": "/browse",
        "surface_id": "browse.product_list",
    }
    assert projection_update["projection"]["graph_node"] == "browse"
    assert _assistant_text(parsed) == "Products ready."


@pytest.mark.asyncio
async def test_chat_projection_is_limited_to_browse_read_operation(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    from langchain_core.messages import AIMessageChunk

    from core.config import Settings
    from services.chat_service import ChatService

    class FakeGraph:
        async def astream_events(self, _graph_input, config, version):
            assert config == {"configurable": {"thread_id": "thread-detail-not-yet"}}
            assert version == "v2"
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": AIMessageChunk(content="I can talk about the T-shirt.")},
            }

    service = ChatService(settings=Settings(openai_api_key="test-key"), graph=FakeGraph())
    route_event_bus.clear()

    parsed = _parse_sse(
        "".join(
            [
                event
                async for event in service.stream(
                    "show me the Medusa T-Shirt",
                    conversation_id="thread-detail-not-yet",
                    route_context={"path": "/", "surface_id": "home.chat"},
                )
            ]
        )
    )

    assert "projection_update" not in [event for event, _data in parsed]
    assert _assistant_text(parsed) == "I can talk about the T-shirt."


def test_default_model_can_be_overridden(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MEDUSA_AGENT_MODEL", "custom-test-model")

    from core.config import Settings

    assert Settings.from_env().medusa_agent_model == "custom-test-model"


def test_settings_load_openai_key_from_local_env_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    from core import config as config_module

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("MEDUSA_AGENT_MODEL", raising=False)
    env_file = tmp_path / "backend.env"
    (tmp_path / "other").mkdir()
    monkeypatch.chdir(tmp_path / "other")
    env_file.write_text(
        "OPENAI_API_KEY=env-file-key\nMEDUSA_AGENT_MODEL=env-file-model\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config_module, "DEFAULT_ENV_PATH", env_file)

    from core.config import Settings

    settings = Settings.from_env()

    assert settings.openai_api_key == "env-file-key"
    assert settings.medusa_agent_model == "env-file-model"


def test_graph_builder_uses_async_concise_streaming_model_call():
    source = (BACKEND_ROOT / "services" / "graph_builder.py").read_text(encoding="utf-8")

    assert "async def agent_node" in source
    assert "await llm.ainvoke" in source
    assert ".bind_tools(MEDUSA_AGENT_TOOLS)" in source
    assert "ToolNode(MEDUSA_AGENT_TOOLS)" in source
    assert "llm.invoke(" not in source
    assert "timeout=settings.model_timeout_seconds" in source
    assert "Keep replies to" in source


def test_open_surface_tool_returns_rendered_product_facts(monkeypatch: pytest.MonkeyPatch):
    import json

    from services import agent_tools as agent_tools_module
    from services.agent_tools import open_medusa_surface

    monkeypatch.setattr(agent_tools_module, "build_runtime_medusa_projection", _fixture_projection)
    payload = json.loads(open_medusa_surface.invoke({"surface_id": "browse.product_list"}))

    assert payload["ok"] is True
    assert payload["surface_intent"] == {"surface_id": "browse.product_list"}
    assert payload["route_context"] == {"path": "/browse", "surface_id": "browse.product_list"}
    assert [product["title"] for product in payload["products"]] == [
        "Medusa T-Shirt",
        "Medusa Sweatshirt",
    ]
    assert "$48.00" in payload["product_facts"]
    assert "Natural, Black, Navy" in payload["product_facts"]
    assert "$78.00" in payload["product_facts"]
    assert "Olive, Charcoal, Black" in payload["product_facts"]
    assert "image_source: medusa_store_api" in payload["product_facts"]


def test_graph_builder_prompt_keeps_current_slice_read_only():
    source = (BACKEND_ROOT / "services" / "graph_builder.py").read_text(encoding="utf-8")

    assert "read-only" in source
    assert "cannot change cart state" in source
    assert "does not render cart controls" in source
    assert "Do not offer cart steps" in source
    assert "Do not offer cart actions" in source
    assert "If the shopper has not explicitly asked about cart" in source
    assert "add an item to your cart" not in source
    assert "manage your cart" not in source


@pytest.mark.asyncio
async def test_graph_errors_are_logged_with_conversation_context(caplog):
    from core.config import Settings
    from services.chat_service import ChatService

    class FailingGraph:
        async def astream_events(self, _input, config, version):
            raise RuntimeError("stream schema mismatch")
            yield

    service = ChatService(
        settings=Settings(openai_api_key="test-key"),
        graph=FailingGraph(),
    )

    with caplog.at_level(logging.ERROR):
        events = [event async for event in service.stream("hi", conversation_id="thread-log")]

    parsed = _parse_sse("".join(events))
    assert parsed[2] == (
        "error",
        {
            "message": "The shopping assistant could not answer that just now.",
            "code": "agent_error",
        },
    )
    assert any(
        record.message == "medusa_agent_stream_failed"
        and getattr(record, "conversation_id") == "thread-log"
        and getattr(record, "error_type") == "RuntimeError"
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_debug_context_thread_records_system_prompt_context_history_and_assistant(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    from langchain_core.messages import AIMessageChunk

    from core.config import Settings
    from services.chat_service import ChatService
    from services.agent_tools import open_medusa_surface

    class FakeGraph:
        async def astream_events(self, _graph_input, config, version):
            assert config == {"configurable": {"thread_id": "debug-thread"}}
            assert version == "v2"
            yield {
                "event": "on_tool_end",
                "data": {"output": open_medusa_surface.invoke({"surface_id": "browse.product_list"})},
            }
            yield {"event": "on_chat_model_stream", "data": {"chunk": AIMessageChunk(content="First ")}}
            yield {"event": "on_chat_model_stream", "data": {"chunk": AIMessageChunk(content="answer.")}}

    service = ChatService(settings=Settings(openai_api_key="test-key"), graph=FakeGraph())
    route_event_bus.clear()

    parsed = _parse_sse(
        "".join(
            [
                event
                async for event in service.stream(
                    "what products do we have?",
                    conversation_id="debug-thread",
                    route_context={"path": "/", "surface_id": "home.chat"},
                )
            ]
        )
    )

    assert "projection_update" not in [event for event, _data in parsed]
    assert route_event_bus.recent("debug-thread")[0]["event_type"] == "projection_update"
    assert _assistant_text(parsed) == "First answer."
    debug_context = service.debug_context_thread("debug-thread")

    assert debug_context["conversation_id"] == "debug-thread"
    assert debug_context["system_prompt"]["role"] == "system"
    assert "You are the Medusa demo shopping assistant." in debug_context["system_prompt"]["content"]
    assert debug_context["latest_route_context"] == {
        "path": "/browse",
        "surface_id": "browse.product_list",
    }
    assert debug_context["latest_accepted_intent"]["reason"] == "browse_products"
    assert debug_context["latest_accepted_intent"]["source"] == "medusa_agent_tool"
    assert debug_context["latest_projection_version"] == 1
    assert [message["role"] for message in debug_context["thread"]] == ["system", "user", "system", "assistant"]
    assert debug_context["thread"][0]["source"] == "routedeck_planning_context"
    assert "home.chat" in debug_context["thread"][0]["content"]
    assert debug_context["thread"][1]["content"] == "what products do we have?"
    assert debug_context["thread"][2]["source"] == "routedeck_planning_context"
    assert "browse.product_list" in debug_context["thread"][2]["content"]
    assert debug_context["thread"][3]["content"] == "First answer."
    assert "prod_" not in str(debug_context)


@pytest.mark.asyncio
async def test_chat_service_reuses_process_local_graph_for_conversation_history(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    from langchain_core.messages import AIMessageChunk

    from core.config import Settings
    from services import graph_builder
    from services.chat_service import ChatService

    class ReusableGraph:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        async def astream_events(self, graph_input, config, version):
            self.calls.append(
                {
                    "graph_input": graph_input,
                    "config": config,
                    "version": version,
                }
            )
            yield {"event": "on_chat_model_stream", "data": {"chunk": AIMessageChunk(content="ok")}}

    built_graphs: list[ReusableGraph] = []

    def fake_build_agent_graph(_settings):
        graph = ReusableGraph()
        built_graphs.append(graph)
        return graph

    monkeypatch.setattr(graph_builder, "build_agent_graph", fake_build_agent_graph)
    service = ChatService(settings=Settings(openai_api_key="test-key"))

    for message in ("hi", "both"):
        list(
            _parse_sse(
                "".join(
                    [
                        event
                        async for event in service.stream(
                            message,
                            conversation_id="history-thread",
                            route_context={"path": "/", "surface_id": "home.chat"},
                        )
                    ]
                )
            )
        )

    assert len(built_graphs) == 1
    assert len(built_graphs[0].calls) == 2
    assert built_graphs[0].calls[0]["config"] == {"configurable": {"thread_id": "history-thread"}}
    assert built_graphs[0].calls[1]["config"] == {"configurable": {"thread_id": "history-thread"}}


def test_backend_runtime_source_has_no_product_write_or_route_deck_public_drift():
    runtime_paths = [
        BACKEND_ROOT / "main.py",
        BACKEND_ROOT / "app.py",
        *sorted((BACKEND_ROOT / "core").glob("*.py")),
        *sorted((BACKEND_ROOT / "routes").glob("*.py")),
        *sorted((BACKEND_ROOT / "services").glob("*.py")),
    ]
    forbidden = re.compile(
        r"routedeck_langgraph|MedusaRouteDeckRuntime|"
        r"routedeck_provider|routedeck_prompt|commerce_state|"
        r"/api/medusa-agent/(state|route-manifest|route-snapshot|action|inspect)|"
        r"/api/routedeck|/admin/|/store/carts|/store/cart|/store/orders"
    )

    hits: list[str] = []
    for path in runtime_paths:
        if forbidden.search(path.name):
            hits.append(str(path.relative_to(BACKEND_ROOT)))
            continue
        text = path.read_text(encoding="utf-8")
        if forbidden.search(text):
            hits.append(str(path.relative_to(BACKEND_ROOT)))

    assert hits == []


def test_chat_service_source_has_no_phrase_router_or_command_map():
    source = (BACKEND_ROOT / "services" / "chat_service.py").read_text(encoding="utf-8")

    assert "_read_surface_target" not in source
    assert "_normalize_message" not in source
    assert "_contains_any" not in source
    assert "words = set" not in source
