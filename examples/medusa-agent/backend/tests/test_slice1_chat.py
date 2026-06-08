from __future__ import annotations

import json
import logging
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


def test_chat_stream_remains_app_owned_after_routedeck_is_added(client: TestClient):
    response = client.get("/api/medusa-agent/route-manifest")

    assert response.status_code == 200
    assert client.post(
        "/api/medusa-agent/agent/stream",
        json={"message": "hi", "conversation_id": "chat-boundary"},
    ).status_code == 200


@pytest.mark.asyncio
async def test_graph_path_maps_conversation_id_to_thread_id_and_injects_routedeck_prompt(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    from langchain_core.messages import AIMessageChunk
    from langchain_core.messages import HumanMessage, SystemMessage

    from core.config import Settings
    from services.chat_service import ChatService
    from services import routedeck_prompt

    async def fake_routedeck_prompt(_settings, session_id: str = "default", runtime=None):
        assert session_id == "thread-123"
        assert runtime is not None
        return "RouteDeck runtime context:\n- legal RouteDeck operations: none"

    monkeypatch.setattr(routedeck_prompt, "build_routedeck_system_prompt", fake_routedeck_prompt)

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
    assert isinstance(fake_graph.input["messages"][0], SystemMessage)
    assert fake_graph.input["messages"][0].content.startswith("RouteDeck runtime context:")
    assert isinstance(fake_graph.input["messages"][1], HumanMessage)
    assert fake_graph.input["messages"][1].content == "hi"
    parsed = _parse_sse("".join(events))
    assert [event for event, _data in parsed].count("message_delta") == 2
    assert _assistant_text(parsed) == "Hello there."
    assert "fallback" not in parsed[0][1]


@pytest.mark.asyncio
async def test_graph_path_forwards_routedeck_events_without_turning_them_into_text(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    from langchain_core.messages import AIMessageChunk
    from routedeck_core import RouteDeckEvent

    from core.config import Settings
    from services.chat_service import ChatService
    from services import routedeck_prompt
    from services import graph_builder

    async def fake_routedeck_prompt(_settings, session_id: str = "default", runtime=None):
        assert session_id == "thread-route"
        assert runtime is not None
        return "Medusa planning context:\n- current node: home"

    monkeypatch.setattr(routedeck_prompt, "build_routedeck_system_prompt", fake_routedeck_prompt)

    class FakeGraph:
        async def astream_events(self, _graph_input, config, version):
            assert config == {"configurable": {"thread_id": "thread-route"}}
            assert version == "v2"
            yield {"event": "on_chat_model_stream", "data": {"chunk": AIMessageChunk(content="Products ready.")}}

    def fake_build_agent_graph(settings, session_id="default", runtime=None, route_event_sink=None):
        assert session_id == "thread-route"
        assert runtime is not None
        assert route_event_sink is not None
        route_event_sink(
            RouteDeckEvent(
                event_type="operation_completed",
                projection_version=2,
                payload={
                    "operation_id": "catalog.list",
                    "state": {
                        "projection": {
                            "current_context": "browse",
                            "graph_node": "browse",
                            "projection_version": 2,
                            "legal_operations": [],
                            "surfaces": {},
                            "presentation_state": {},
                            "diagnostics": {},
                        },
                        "status": "idle",
                    },
                },
            )
        )
        return FakeGraph()

    monkeypatch.setattr(graph_builder, "build_agent_graph", fake_build_agent_graph)

    service = ChatService(settings=Settings(openai_api_key="test-key"))

    parsed = _parse_sse("".join([event async for event in service.stream("show products", conversation_id="thread-route")]))

    assert [event for event, _data in parsed] == [
        "stream_start",
        "agent_start",
        "routedeck_event",
        "message_delta",
        "agent_end",
        "stream_end",
    ]
    route_event = parsed[2][1]
    assert route_event["event_type"] == "operation_completed"
    assert route_event["payload"]["state"]["projection"]["graph_node"] == "browse"
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
