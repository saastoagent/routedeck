from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


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


def _assistant_text(events: list[tuple[str, dict]]) -> str:
    return "".join(data["content"] for event, data in events if event == "message_delta")


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
        ("GET", "/api/medusa-agent/projection"),
        ("POST", "/api/medusa-agent/action"),
        ("POST", "/api/medusa-agent/inspect"),
        ("GET", "/api/medusa-agent/route-stream"),
        ("GET", "/api/routedeck/anything"),
        ("POST", "/api/routedeck/anything"),
    ]

    for method, path in forbidden_routes:
        response = client.request(method, path, json={} if method == "POST" else None)
        assert response.status_code == 404, f"{method} {path} must not exist in Slice 1"


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

    class FakeGraph:
        async def astream_events(self, _graph_input, config, version):
            assert config == {"configurable": {"thread_id": "thread-route"}}
            assert version == "v2"
            yield {"event": "on_tool_start", "data": {"name": "ignored"}}
            yield {"event": "on_chat_model_stream", "data": {"chunk": AIMessageChunk(content="Products ready.")}}

    service = ChatService(settings=Settings(openai_api_key="test-key"), graph=FakeGraph())

    parsed = _parse_sse("".join([event async for event in service.stream("show products", conversation_id="thread-route")]))

    assert [event for event, _data in parsed] == [
        "stream_start",
        "agent_start",
        "message_delta",
        "agent_end",
        "stream_end",
    ]
    assert _assistant_text(parsed) == "Products ready."


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
    assert "llm.invoke(" not in source
    assert "timeout=settings.model_timeout_seconds" in source
    assert "Keep replies to" in source


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


def test_slice1_backend_runtime_source_has_no_later_slice_imports_or_routes():
    runtime_paths = [
        BACKEND_ROOT / "main.py",
        BACKEND_ROOT / "app.py",
        *sorted((BACKEND_ROOT / "core").glob("*.py")),
        *sorted((BACKEND_ROOT / "routes").glob("*.py")),
        *sorted((BACKEND_ROOT / "services").glob("*.py")),
    ]
    forbidden = re.compile(
        r"routedeck_core|routedeck_langgraph|RouteDeck|MedusaRouteDeckRuntime|"
        r"routedeck_provider|routedeck_prompt|agent_tools|medusa_store|commerce_state|"
        r"/api/medusa-agent/(state|route-manifest|route-snapshot|projection|action|inspect|route-stream)|"
        r"/api/routedeck"
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
