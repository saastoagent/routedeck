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
    from routes import routedeck as routedeck_route
    from services.routedeck_runtime import MedusaRouteDeckRuntime

    routedeck_route.runtime = MedusaRouteDeckRuntime(settings=config_module.Settings.from_env())

    return TestClient(app)


def test_slice3_manifest_defines_browse_detail_and_cart_without_future_scope(client: TestClient):
    response = client.get("/api/medusa-agent/route-manifest")

    assert response.status_code == 200
    manifest = response.json()
    assert manifest["version"] == "medusa-agent-slice3"
    assert [node["id"] for node in manifest["nodes"]] == ["home", "browse", "detail", "cart"]
    assert manifest["nodes"][0]["default_surfaces"]["active"] == "agent_home"
    assert any(edge["from"] == "home" and edge["to"] == "browse" for edge in manifest["edges"])
    assert [action["id"] for action in manifest["actions"]] == [
        "catalog.list",
        "catalog.open",
        "variant.select",
        "cart.create",
        "cart.add_item",
        "cart.view",
    ]
    assert "/api/routedeck" not in response.text
    assert "checkout" not in response.text.lower()
    assert "payment" not in response.text.lower()
    assert "shipping" not in response.text.lower()
    assert "admin" not in response.text.lower()


def test_projection_has_no_product_operations_when_setup_is_not_ready(client: TestClient):
    response = client.get("/api/medusa-agent/projection?session_id=offline-session")

    assert response.status_code == 200
    projection = response.json()
    assert projection["graph_node"] == "home"
    assert projection["legal_operations"] == []
    assert projection["surfaces"]["active"]["variant"] == "setup_status"
    assert "products" not in projection["surfaces"]["active"]["props"]


@pytest.mark.asyncio
async def test_ready_projection_defaults_to_home_with_copyable_deeplink(monkeypatch: pytest.MonkeyPatch):
    from core.config import Settings
    from services.medusa_store import StoreProduct, StoreVariant
    from services.routedeck_runtime import MedusaRouteDeckRuntime

    async def fake_setup(_settings, timeout=2.0):
        return {"setup": {"ready": True, "mode": "local-demo"}, "connections": []}

    class FakeStoreClient:
        async def list_products(self, limit=12):
            return [
                StoreProduct(
                    id="prod_private",
                    title="Medusa T-Shirt",
                    handle="medusa-t-shirt",
                    variants=[StoreVariant(id="variant_private", title="M")],
                )
            ]

    monkeypatch.setattr("services.routedeck_runtime.probe_medusa_setup", fake_setup)
    runtime = MedusaRouteDeckRuntime(
        settings=Settings(medusa_publishable_api_key="pk_test"),
        store_client=FakeStoreClient(),
    )

    projection = await runtime.projection(context={"session_id": "s1"})
    payload = projection.model_dump(mode="json")

    assert payload["graph_node"] == "home"
    assert payload["surfaces"]["active"]["variant"] == "agent_home"
    assert [operation["id"] for operation in payload["legal_operations"]] == ["catalog.list", "cart.view"]
    assert payload["navigation"]["current"]["deeplink"]["url"] == "/"
    assert [node["id"] for node in payload["navgraph"]["nodes"]] == ["home", "browse", "detail", "cart"]
    assert payload["navgraph"]["nodes"][0]["metadata"]["allowed_actions"] == ["catalog.list", "cart.view"]


@pytest.mark.asyncio
async def test_ready_projection_exposes_sanitized_products(monkeypatch: pytest.MonkeyPatch):
    from core.config import Settings
    from services.medusa_store import StoreProduct, StoreVariant
    from services.routedeck_runtime import MedusaRouteDeckRuntime

    async def fake_setup(_settings, timeout=2.0):
        return {"setup": {"ready": True, "mode": "local-demo"}, "connections": []}

    class FakeStoreClient:
        async def list_products(self, limit=12):
            return [
                StoreProduct(
                    id="prod_private",
                    title="Medusa T-Shirt",
                    handle="medusa-t-shirt",
                    variants=[StoreVariant(id="variant_private", title="M")],
                )
            ]

    monkeypatch.setattr("services.routedeck_runtime.probe_medusa_setup", fake_setup)
    runtime = MedusaRouteDeckRuntime(
        settings=Settings(medusa_publishable_api_key="pk_test"),
        store_client=FakeStoreClient(),
    )

    projection = await runtime.projection(context={"session_id": "s1", "rd_node": "browse"})
    payload = projection.model_dump(mode="json")

    assert [operation.id for operation in projection.legal_operations] == ["catalog.list", "catalog.open", "cart.view"]
    assert projection.legal_operations[1].can_dispatch_now is False
    assert projection.legal_operations[1].missing_args == ["entity_key"]
    assert payload["surfaces"]["active"]["variant"] == "product_list"
    assert payload["surfaces"]["active"]["props"]["products"][0]["title"] == "Medusa T-Shirt"
    assert payload["surfaces"]["active"]["props"]["products"][0]["entity_key"].startswith("product:entity_")
    assert payload["surfaces"]["active"]["props"]["products"][0]["variants"][0]["entity_key"].startswith("variant:entity_")
    assert payload["available_entities"][0]["operations"][0]["operation_id"] == "catalog.open"
    assert payload["surface_affordances"][0]["surface_id"] == "browse.product_list"
    assert payload["surface_affordances"][0]["affordance_id"] == "view_product"
    assert [capability["capability_id"] for capability in payload["capabilities"]] == [
        "catalog.browse",
        "product.configure",
        "cart.manage",
    ]
    assert [edge["action_id"] for edge in payload["navgraph"]["edges"]]
    assert payload["navigation"]["current"]["deeplink"]["url"] == "/browse"
    assert payload["navgraph"]["nodes"][0]["deeplink"]["url"] == "/"
    assert payload["navgraph"]["nodes"][1]["deeplink"]["url"] == "/browse"
    assert payload["navgraph"]["nodes"][3]["deeplink"]["url"] == "/cart"
    assert "prod_private" not in str(payload)
    assert "variant_private" not in str(payload)
    assert "product_ref" not in str(payload["surfaces"]["active"]["props"])
    assert "variant_ref" not in str(payload["surfaces"]["active"]["props"])


@pytest.mark.asyncio
async def test_accepted_dispatch_events_carry_client_applicable_state(monkeypatch: pytest.MonkeyPatch):
    from routedeck_core import RouteDeckDispatchInput

    from core.config import Settings
    from services.medusa_store import StoreProduct, StoreVariant
    from services.routedeck_runtime import MedusaRouteDeckRuntime

    async def fake_setup(_settings, timeout=2.0):
        return {"setup": {"ready": True, "mode": "local-demo"}, "connections": []}

    class FakeStoreClient:
        async def list_products(self, limit=12):
            return [
                StoreProduct(
                    id="prod_private",
                    title="Medusa T-Shirt",
                    handle="medusa-t-shirt",
                    variants=[StoreVariant(id="variant_private", title="M")],
                )
            ]

    monkeypatch.setattr("services.routedeck_runtime.probe_medusa_setup", fake_setup)
    runtime = MedusaRouteDeckRuntime(
        settings=Settings(medusa_publishable_api_key="pk_test"),
        store_client=FakeStoreClient(),
    )

    result = await runtime.dispatch(
        RouteDeckDispatchInput(operation_id="catalog.list", args={}),
        context={"session_id": "s1"},
    )

    event = result.events[0]
    assert event.event_type == "operation_completed"
    assert event.payload["operation_id"] == "catalog.list"
    assert event.payload["state"]["projection"]["graph_node"] == "browse"
    assert event.payload["state"]["projection"]["navgraph"]["current"]["node_id"] == "browse"
    assert event.payload["state"]["projection"]["navigation"]["current"]["deeplink"]["url"] == "/browse"


@pytest.mark.asyncio
async def test_agent_dispatch_updates_followup_planning_projection(monkeypatch: pytest.MonkeyPatch):
    from routedeck_core import RouteDeckDispatchInput

    from core.config import Settings
    from services.medusa_store import StoreProduct, StoreVariant
    from services.routedeck_prompt import build_routedeck_system_prompt
    from services.routedeck_runtime import MedusaRouteDeckRuntime

    async def fake_setup(_settings, timeout=2.0):
        return {"setup": {"ready": True, "mode": "local-demo"}, "connections": []}

    class FakeStoreClient:
        async def list_products(self, limit=12):
            return [
                StoreProduct(
                    id="prod_private",
                    title="Medusa T-Shirt",
                    handle="medusa-t-shirt",
                    variants=[StoreVariant(id="variant_private", title="M")],
                )
            ]

    monkeypatch.setattr("services.routedeck_runtime.probe_medusa_setup", fake_setup)
    runtime = MedusaRouteDeckRuntime(
        settings=Settings(medusa_publishable_api_key="pk_test"),
        store_client=FakeStoreClient(),
    )

    await runtime.dispatch(
        RouteDeckDispatchInput(operation_id="catalog.list", args={}),
        context={"session_id": "s1", "source": "agent_tool"},
    )
    prompt = await build_routedeck_system_prompt(Settings(openai_api_key="test-key"), session_id="s1", runtime=runtime)

    assert "- active surface: product_list" in prompt
    assert "Medusa T-Shirt" in prompt
    assert "entity_key: product:" in prompt


@pytest.mark.asyncio
async def test_projection_resumes_product_detail_from_copyable_deeplink(monkeypatch: pytest.MonkeyPatch):
    from core.config import Settings
    from services.medusa_store import StoreProduct, StoreVariant
    from services.routedeck_runtime import MedusaRouteDeckRuntime

    async def fake_setup(_settings, timeout=2.0):
        return {"setup": {"ready": True, "mode": "local-demo"}, "connections": []}

    class FakeStoreClient:
        async def list_products(self, limit=12):
            return [
                StoreProduct(
                    id="prod_private",
                    title="Medusa T-Shirt",
                    handle="medusa-t-shirt",
                    variants=[StoreVariant(id="variant_private", title="M")],
                )
            ]

        async def get_product(self, product_id: str):
            assert product_id == "prod_private"
            return StoreProduct(
                id="prod_private",
                title="Medusa T-Shirt",
                handle="medusa-t-shirt",
                variants=[StoreVariant(id="variant_private", title="M")],
            )

    monkeypatch.setattr("services.routedeck_runtime.probe_medusa_setup", fake_setup)
    runtime = MedusaRouteDeckRuntime(
        settings=Settings(medusa_publishable_api_key="pk_test"),
        store_client=FakeStoreClient(),
    )

    projection = await runtime.projection(
        context={"session_id": "s1", "rd_node": "detail", "rd_product": "medusa-t-shirt"}
    )
    payload = projection.model_dump(mode="json")

    assert payload["graph_node"] == "detail"
    assert payload["surfaces"]["active"]["variant"] == "product_detail"
    assert payload["surfaces"]["active"]["props"]["product"]["title"] == "Medusa T-Shirt"
    assert payload["navigation"]["current"]["deeplink"]["url"] == "/detail/medusa-t-shirt"
    assert payload["navgraph"]["current"]["deeplink"]["url"] == "/detail/medusa-t-shirt"
    assert "prod_private" not in str(payload)
    assert "variant_private" not in str(payload)


@pytest.mark.asyncio
async def test_dispatch_open_select_and_add_item_use_opaque_refs(monkeypatch: pytest.MonkeyPatch):
    from routedeck_core import RouteDeckDispatchInput, RouteDeckSurfaceInteractionEvent

    from core.config import Settings
    from services.medusa_store import StoreCart, StoreCartItem, StoreProduct, StoreRegion, StoreVariant
    from services.routedeck_runtime import MedusaRouteDeckRuntime

    async def fake_setup(_settings, timeout=2.0):
        return {"setup": {"ready": True, "mode": "local-demo"}, "connections": []}

    class FakeStoreClient:
        async def list_products(self, limit=12):
            return [StoreProduct(id="prod_private", title="Medusa T-Shirt", variants=[StoreVariant(id="variant_private", title="M")])]

        async def get_product(self, product_id: str):
            assert product_id == "prod_private"
            return StoreProduct(id="prod_private", title="Medusa T-Shirt", variants=[StoreVariant(id="variant_private", title="M")])

        async def first_region(self):
            return StoreRegion(id="reg_private", currency_code="usd")

        async def create_cart(self, region_id: str):
            assert region_id == "reg_private"
            return StoreCart(id="cart_private", items=[])

        async def add_line_item(self, cart_id: str, variant_id: str, quantity: int):
            assert cart_id == "cart_private"
            assert variant_id == "variant_private"
            assert quantity == 2
            return StoreCart(id="cart_private", items=[StoreCartItem(id="line_private", title="Medusa T-Shirt", quantity=2)])

    monkeypatch.setattr("services.routedeck_runtime.probe_medusa_setup", fake_setup)
    runtime = MedusaRouteDeckRuntime(
        settings=Settings(medusa_publishable_api_key="pk_test"),
        store_client=FakeStoreClient(),
    )
    projection = await runtime.projection({"session_id": "s1", "rd_node": "browse"})
    product_entity_key = projection.surfaces["active"].props["products"][0]["entity_key"]

    opened = await runtime.dispatch(
        RouteDeckDispatchInput(
            surface_event=RouteDeckSurfaceInteractionEvent(
                surface_id="browse.product_list",
                affordance_id="view_product",
                entity_key=product_entity_key,
            )
        ),
        context={"session_id": "s1", "source": "test"},
    )
    variant_entity_key = opened.state.projection.surfaces["active"].props["product"]["variants"][0]["entity_key"]
    selected = await runtime.dispatch(
        RouteDeckDispatchInput(
            surface_event=RouteDeckSurfaceInteractionEvent(
                surface_id="detail.product_detail",
                affordance_id="select_variant",
                entity_key=variant_entity_key,
            )
        ),
        context={"session_id": "s1", "source": "test"},
    )
    added = await runtime.dispatch(
        RouteDeckDispatchInput(
            surface_event=RouteDeckSurfaceInteractionEvent(
                surface_id="detail.product_detail",
                affordance_id="add_variant_to_cart",
                entity_key=variant_entity_key,
                payload={"quantity": 2},
            )
        ),
        context={"session_id": "s1", "source": "test"},
    )

    assert opened.accepted is True
    assert selected.accepted is True
    assert added.accepted is True
    assert added.active_surface is not None
    assert added.active_surface.variant == "cart_summary"
    assert added.messages == [{"content": "Added to cart."}]
    payload = added.model_dump(mode="json")
    assert "prod_private" not in str(payload)
    assert "variant_private" not in str(payload)
    assert "cart_private" not in str(payload)
    assert "line_private" not in str(payload)
    assert "cart_ref" not in str(payload["active_surface"]["props"])


@pytest.mark.asyncio
async def test_cart_add_item_requires_variant_and_quantity(monkeypatch: pytest.MonkeyPatch):
    from routedeck_core import RouteDeckDispatchInput

    from core.config import Settings
    from services.medusa_store import StoreProduct, StoreVariant
    from services.routedeck_runtime import MedusaRouteDeckRuntime

    async def fake_setup(_settings, timeout=2.0):
        return {"setup": {"ready": True, "mode": "local-demo"}, "connections": []}

    class FakeStoreClient:
        async def list_products(self, limit=12):
            return [StoreProduct(id="prod_private", title="Medusa T-Shirt", variants=[StoreVariant(id="variant_private", title="M")])]

    monkeypatch.setattr("services.routedeck_runtime.probe_medusa_setup", fake_setup)
    runtime = MedusaRouteDeckRuntime(
        settings=Settings(medusa_publishable_api_key="pk_test"),
        store_client=FakeStoreClient(),
    )

    result = await runtime.dispatch(
        RouteDeckDispatchInput(operation_id="cart.add_item", args={}),
        context={"session_id": "s1", "source": "test"},
    )

    assert result.accepted is False
    assert result.messages == [{"content": "Choose a variant and quantity before adding an item to cart."}]
    assert result.events[0].event_type == "guard_failure"


def test_snapshot_inspect_and_stream_accept_session_id_without_public_echo(client: TestClient):
    snapshot = client.get("/api/medusa-agent/route-snapshot?session_id=session-abc")
    inspect = client.post("/api/medusa-agent/inspect?session_id=session-abc", json={"surface": "active"})

    with client.stream("GET", "/api/medusa-agent/route-stream?session_id=session-abc") as response:
        stream_text = next(response.iter_text())

    assert snapshot.status_code == 200
    assert inspect.status_code == 200
    assert "session-abc" not in snapshot.text
    assert "session-abc" not in inspect.text
    assert "session-abc" not in stream_text


def test_dispatch_merges_context_and_preserves_session_id_without_public_echo(client: TestClient):
    response = client.post(
        "/api/medusa-agent/action",
        json={
            "operation_id": "catalog.list",
            "args": {},
            "context": {"session_id": "session-abc", "source": "ui"},
        },
    )

    assert response.status_code in {200, 400}
    assert "session-abc" not in response.text
