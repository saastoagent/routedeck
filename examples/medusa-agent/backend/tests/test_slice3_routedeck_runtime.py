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
    response = client.get("/api/routedeck/manifest")

    assert response.status_code == 200
    manifest = response.json()
    assert manifest["version"] == "medusa-agent-slice3"
    assert [node["id"] for node in manifest["nodes"]] == ["browse", "detail", "cart"]
    assert [action["id"] for action in manifest["actions"]] == [
        "catalog.list",
        "catalog.open",
        "variant.select",
        "cart.create",
        "cart.add_item",
        "cart.view",
    ]
    assert "/api/routedeck/medusa" not in response.text
    assert "checkout" not in response.text.lower()
    assert "payment" not in response.text.lower()
    assert "shipping" not in response.text.lower()
    assert "admin" not in response.text.lower()


def test_projection_has_no_product_operations_when_setup_is_not_ready(client: TestClient):
    response = client.get("/api/routedeck/projection?session_id=offline-session")

    assert response.status_code == 200
    projection = response.json()
    assert projection["legal_operations"] == []
    assert projection["surfaces"]["active"]["variant"] == "setup_status"
    assert "products" not in projection["surfaces"]["active"]["props"]


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

    assert [operation.id for operation in projection.legal_operations] == ["catalog.list", "catalog.open", "cart.view"]
    assert payload["surfaces"]["active"]["variant"] == "product_list"
    assert payload["surfaces"]["active"]["props"]["products"][0]["title"] == "Medusa T-Shirt"
    assert payload["surfaces"]["active"]["props"]["products"][0]["product_ref"].startswith("product_")
    assert "prod_private" not in str(payload)
    assert "variant_private" not in str(payload)


@pytest.mark.asyncio
async def test_dispatch_open_select_and_add_item_use_opaque_refs(monkeypatch: pytest.MonkeyPatch):
    from routedeck_core import RouteDeckDispatchInput

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
    projection = await runtime.projection({"session_id": "s1"})
    product_ref = projection.surfaces["active"].props["products"][0]["product_ref"]
    variant_ref = projection.surfaces["active"].props["products"][0]["variants"][0]["variant_ref"]

    opened = await runtime.dispatch(
        RouteDeckDispatchInput(operation_id="catalog.open", args={"product_ref": product_ref}),
        context={"session_id": "s1", "source": "test"},
    )
    selected = await runtime.dispatch(
        RouteDeckDispatchInput(operation_id="variant.select", args={"variant_ref": variant_ref}),
        context={"session_id": "s1", "source": "test"},
    )
    added = await runtime.dispatch(
        RouteDeckDispatchInput(operation_id="cart.add_item", args={"variant_ref": variant_ref, "quantity": 2}),
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
    snapshot = client.get("/api/routedeck/snapshot?session_id=session-abc")
    inspect = client.post("/api/routedeck/inspect?session_id=session-abc", json={"surface": "active"})

    with client.stream("GET", "/api/routedeck/stream?session_id=session-abc") as response:
        stream_text = next(response.iter_text())

    assert snapshot.status_code == 200
    assert inspect.status_code == 200
    assert "session-abc" not in snapshot.text
    assert "session-abc" not in inspect.text
    assert "session-abc" not in stream_text


def test_dispatch_merges_context_and_preserves_session_id_without_public_echo(client: TestClient):
    response = client.post(
        "/api/routedeck/dispatch",
        json={
            "operation_id": "catalog.list",
            "args": {},
            "context": {"session_id": "session-abc", "source": "ui"},
        },
    )

    assert response.status_code in {200, 400}
    assert "session-abc" not in response.text
