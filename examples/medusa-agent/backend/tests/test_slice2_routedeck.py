from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
ROUTEDECK_ROOT = BACKEND_ROOT.parents[2]
for path in (BACKEND_ROOT, ROUTEDECK_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    from core import config as config_module

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("MEDUSA_AGENT_MODEL", raising=False)
    monkeypatch.delenv("MEDUSA_BACKEND_URL", raising=False)
    monkeypatch.delenv("MEDUSA_STOREFRONT_URL", raising=False)
    monkeypatch.delenv("MEDUSA_PUBLISHABLE_API_KEY", raising=False)
    monkeypatch.setattr(config_module, "DEFAULT_ENV_PATH", tmp_path / "missing.env")
    monkeypatch.chdir(tmp_path)

    from app import app
    from services import chat_service as chat_service_module

    chat_service_module.chat_service.settings = config_module.Settings.from_env()
    chat_service_module.chat_service.graph = None

    return TestClient(app)


def test_routedeck_manifest_is_generic_and_slice3_scoped(client: TestClient):
    response = client.get("/api/routedeck/manifest")

    assert response.status_code == 200
    manifest = response.json()
    assert manifest["version"] == "medusa-agent-slice3"
    assert [node["id"] for node in manifest["nodes"]] == ["browse", "detail", "cart"]
    assert "/api/routedeck/medusa" not in response.text
    assert "checkout" not in response.text.lower()
    assert "payment" not in response.text.lower()
    assert "shipping" not in response.text.lower()
    assert "admin" not in response.text.lower()


def test_projection_exposes_setup_status_and_blocks_unavailable_connection(client: TestClient):
    response = client.get("/api/routedeck/projection")

    assert response.status_code == 200
    projection = response.json()
    assert projection["graph_node"] == "browse"
    assert "active" in projection["surfaces"]
    assert projection["surfaces"]["active"]["variant"] == "setup_status"
    assert projection["legal_operations"] == []
    assert "diagnostics" not in projection["surfaces"]["active"]


def test_medusa_agent_state_reports_setup_not_commerce_state(client: TestClient):
    response = client.get("/api/medusa-agent/state")

    assert response.status_code == 200
    state = response.json()
    assert set(state) >= {"setup", "connections"}
    assert "cart" not in state
    assert "checkout" not in state


def test_dispatch_rejects_all_operation_execution_in_slice2(client: TestClient):
    response = client.post("/api/routedeck/dispatch", json={"operation_id": "medusa.setup.refresh", "args": {}})

    assert response.status_code == 400
    assert response.json()["detail"] == "Unknown RouteDeck operation: medusa.setup.refresh"


def test_inspect_returns_framework_guard_without_future_command_catalog(client: TestClient):
    response = client.post("/api/routedeck/inspect", json={})

    assert response.status_code == 200
    body = response.json()
    assert "introspection" in body
    assert "guard_explanations" in body["introspection"]
    assert body["introspection"]["legal_operations"] == []
    assert body["introspection"]["blocked_operations"] == []
    assert all("id" not in blocked for blocked in body["introspection"]["blocked_operations"])


def test_routedeck_stream_is_sse_projection_update(client: TestClient):
    with client.stream("GET", "/api/routedeck/stream") as response:
        assert response.status_code == 200
        first = next(response.iter_text())

    assert "event: projection_update" in first


@pytest.mark.asyncio
async def test_routedeck_prompt_reflects_projection_without_future_catalog(monkeypatch: pytest.MonkeyPatch):
    from routedeck_core import RouteDeckLocation, RouteDeckNavigationState, RouteDeckProjection, RouteDeckSurface

    from core.config import Settings
    from services import routedeck_prompt

    projection = RouteDeckProjection(
        current_context="setup",
        graph_node="setup",
        legal_operations=[],
        surfaces={
            "active": RouteDeckSurface(
                name="active",
                component="MedusaSetupPanel",
                variant="setup_status",
                props={"setup": {"ready": False, "mode": "local-demo"}},
            )
        },
        navigation=RouteDeckNavigationState(current=RouteDeckLocation(node_id="setup")),
    )

    class FakeRuntime:
        def __init__(self, settings):
            self.settings = settings

        async def projection(self, context=None):
            assert context == {"probe_timeout": 0.5, "session_id": "default"}
            return projection

    monkeypatch.setattr(routedeck_prompt, "MedusaRouteDeckRuntime", FakeRuntime)

    prompt = await routedeck_prompt.build_routedeck_system_prompt(Settings(openai_api_key="test-key"))

    assert "RouteDeck runtime context:" in prompt
    assert "setup ready: false" in prompt
    assert "legal RouteDeck operations: none" in prompt
    assert "Do not invent catalog items" in prompt
    assert "cart.create" not in prompt
    assert "checkout.start" not in prompt
