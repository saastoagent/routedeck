# Medusa Agent Slice 3 Product Browse And Cart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add real local/demo Medusa product browse, variant selection, and cart add behavior through shared RouteDeck dispatch without introducing checkout, payment, shipping, admin, Docker, or fake catalog behavior.

**Architecture:** Slice 3 keeps chat under `/api/medusa-agent/*` and RouteDeck contracts under `/api/routedeck/*`. Medusa HTTP calls live in app-owned adapter services, while RouteDeck owns projection, legal operation readiness, dispatch validation, and operation events. The React UI and LangGraph agent tools must call the same `MedusaRouteDeckRuntime.dispatch()` path; the agent learns available capabilities from the RouteDeck system prompt, not from phrase routing or hardcoded product answers.

**Tech Stack:** FastAPI, pytest, httpx, LangGraph, `langchain-openai`, RouteDeck core Python contracts, React, Vite, Vitest, Testing Library, local/demo Medusa Store API.

---

## Scope

Build only Slice 3:

- Keep `POST /api/medusa-agent/agent/stream` app-owned and chat-first.
- Keep generic RouteDeck endpoints under `/api/routedeck/*`.
- Add app-owned Medusa Store API adapter for:
  - `GET /store/products`
  - `GET /store/products/{id}`
  - `GET /store/regions` only as a cart prerequisite.
  - `POST /store/carts`
  - `POST /store/carts/{id}/line-items`
- Require `MEDUSA_BACKEND_URL` and `MEDUSA_PUBLISHABLE_API_KEY` for live browse/cart operations.
- Add typed RouteDeck operations only when setup is ready and backing Medusa data exists.
- Add product list, product detail, variant selection, and cart summary surfaces derived from RouteDeck projection.
- Add LangGraph tools that dispatch the same RouteDeck operations as UI clicks.
- Preserve private Medusa IDs behind server-side opaque refs. Public UI and chat may show product names, options, prices, and quantities, but not raw `prod_*`, `variant_*`, `cart_*`, or line item ids.
- Do not add checkout, payment, shipping-option selection, fulfillment, admin mutation, seeded catalog reset, Docker, or external production data.

## Lessons From Slices 1-2

- Do not fake product lists. If Medusa is not connected, RouteDeck legal operations are empty and the agent must say browsing is unavailable in product language.
- Do not solve capability gaps by hardcoding denial text into the base commerce prompt. RouteDeck prompt context must describe current projection, setup readiness, and legal operations.
- Do not add phrase tables or deterministic command routing for chat. The LLM chooses tools; tools validate through RouteDeck dispatch.
- Do not make the app a RouteDeck debugger. Product UI can show product cards and cart state, but it must not show operation IDs, graph nodes, endpoint paths, dispatch traces, diagnostics, or blocked future actions.
- Keep RouteDeck deterministic where it should be deterministic: typed operation validation, missing-argument guards, state projection, and dispatch results.

## File Structure

- Modify `examples/medusa-agent/backend/core/config.py`: keep Slice 2 settings and confirm `MEDUSA_PUBLISHABLE_API_KEY` is loaded from env or `.env`.
- Create `examples/medusa-agent/backend/services/medusa_store.py`: app-owned Store API client with product, variant, region, cart, and line-item methods.
- Create `examples/medusa-agent/backend/services/commerce_refs.py`: process-local opaque reference mapper for product, variant, cart, and line item IDs.
- Create `examples/medusa-agent/backend/services/commerce_state.py`: process-local per-session browse/cart state used by runtime projection and dispatch.
- Modify `examples/medusa-agent/backend/services/routedeck_manifest.py`: replace setup-only manifest with browse/detail/cart nodes and allowed action specs.
- Modify `examples/medusa-agent/backend/services/routedeck_runtime.py`: project product/cart surfaces and implement typed dispatch.
- Modify `examples/medusa-agent/backend/services/routedeck_prompt.py`: describe legal RouteDeck operation labels and capability state without leaking operation IDs to the shopper.
- Create `examples/medusa-agent/backend/services/agent_tools.py`: LangGraph tool definitions that call `MedusaRouteDeckRuntime.dispatch()`.
- Modify `examples/medusa-agent/backend/services/graph_builder.py`: bind agent tools to the LLM while preserving the app-owned commerce prompt.
- Modify `examples/medusa-agent/backend/services/chat_service.py`: pass `conversation_id` as RouteDeck `session_id` to prompt and tools.
- Modify `examples/medusa-agent/backend/tests/test_slice3_medusa_store.py`: Store API adapter and opaque-ref tests with `httpx.MockTransport`.
- Modify `examples/medusa-agent/backend/tests/test_slice3_routedeck_runtime.py`: projection, dispatch, guards, and no-fake-catalog tests.
- Modify `examples/medusa-agent/backend/tests/test_slice1_chat.py` and `test_slice2_routedeck.py`: preserve earlier behavior where still applicable; update only stale Slice 2 assumptions.
- Create `examples/medusa-agent/frontend/src/hooks/useRouteDeckProjection.ts`: fetch projection and dispatch typed RouteDeck operation requests.
- Modify `examples/medusa-agent/frontend/src/App.tsx`: render chat-first product browse/detail/cart surfaces without RouteDeck internals.
- Modify `examples/medusa-agent/frontend/src/App.test.tsx`: add product/card/cart UI tests and anti-debugger assertions.
- Modify `examples/medusa-agent/frontend/src/styles.css`: add compact product/card/cart layout.
- Modify `examples/medusa-agent/README.md`: document Slice 3 env, operation scope, local Medusa requirement, and non-goals.
- Modify `docs/medusa-agent-reference-app.md`: link this plan under Slice 3 and clarify Slice 3 authority.
- Modify `tests/test_medusa_reference_slice0.py`: allow Slice 3 browse/cart implementation while continuing to ban checkout/payment/shipping/admin and product-specific RouteDeck routes.

## Execution Checkpoints

Use subagents for execution, but do not hand a whole large task to one subagent
without review. Split Task 5 into manifest, projection, and dispatch checkpoints.
Split Task 8 into hook, product list/detail, cart controls, and visual/browser
smoke checkpoints. After each checkpoint, run the narrow tests named in that
task before continuing.

## Operation Contract

Allowed Slice 3 RouteDeck operations:

- `catalog.list`: read product list from local/demo Medusa.
- `catalog.open`: open product detail from an opaque `product_ref`.
- `variant.select`: select an opaque `variant_ref` for the current product.
- `cart.create`: create a local/demo cart when needed.
- `cart.add_item`: add selected variant and quantity to cart.
- `cart.view`: read current cart summary.

Operation authority:

- `catalog.list`, `catalog.open`, and `cart.view` are read operations and may run when setup is ready.
- `variant.select` is state selection, not a Medusa write.
- `cart.create` and `cart.add_item` are local/demo Medusa writes. They require explicit user intent from chat or a direct UI click. No silent cart mutation from a greeting or vague browse request.
- `cart.add_item` must require `variant_ref` and `quantity`. Missing variant or quantity returns a guard failure and product-language guidance.

Blocked or absent operations:

- Any operation containing checkout, payment, shipping, fulfillment, admin, order completion, refund, cancel, delete, or reset.
- Any product-specific RouteDeck route such as `/api/routedeck/medusa/*`.
- Any operation that requires production data or external payment/shipping side effects.

## Task 1: Backend Store Adapter Tests

**Files:**

- Create: `examples/medusa-agent/backend/tests/test_slice3_medusa_store.py`
- Create: `examples/medusa-agent/backend/services/medusa_store.py`

- [ ] Write failing tests for Store API headers and product normalization:

```python
import httpx
import pytest

from core.config import Settings
from services.medusa_store import MedusaStoreClient


@pytest.mark.asyncio
async def test_list_products_uses_publishable_key_and_normalizes_public_fields():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["x-publishable-api-key"] == "pk_test"
        assert request.url.path == "/store/products"
        return httpx.Response(
            200,
            json={
                "products": [
                    {
                        "id": "prod_1",
                        "title": "Medusa T-Shirt",
                        "thumbnail": "https://example.test/shirt.png",
                        "variants": [
                            {"id": "variant_1", "title": "M", "options": [{"value": "M"}]},
                        ],
                    }
                ]
            },
        )

    client = MedusaStoreClient(
        Settings(medusa_backend_url="http://medusa.test", medusa_publishable_api_key="pk_test"),
        transport=httpx.MockTransport(handler),
    )

    products = await client.list_products(limit=12)

    assert len(requests) == 1
    assert products[0].id == "prod_1"
    assert products[0].title == "Medusa T-Shirt"
    assert products[0].variants[0].id == "variant_1"
```

- [ ] Write failing tests for cart creation and add line item:

```python
@pytest.mark.asyncio
async def test_create_cart_and_add_line_item_call_store_api():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path, request.content))
        if request.url.path == "/store/regions":
            return httpx.Response(200, json={"regions": [{"id": "reg_1", "currency_code": "usd"}]})
        if request.url.path == "/store/carts":
            return httpx.Response(200, json={"cart": {"id": "cart_1", "items": []}})
        if request.url.path == "/store/carts/cart_1/line-items":
            return httpx.Response(
                200,
                json={"cart": {"id": "cart_1", "items": [{"id": "li_1", "quantity": 2, "title": "Medusa T-Shirt"}]}},
            )
        return httpx.Response(404)

    client = MedusaStoreClient(
        Settings(medusa_backend_url="http://medusa.test", medusa_publishable_api_key="pk_test"),
        transport=httpx.MockTransport(handler),
    )

    region = await client.first_region()
    cart = await client.create_cart(region_id=region.id)
    updated = await client.add_line_item(cart_id=cart.id, variant_id="variant_1", quantity=2)

    assert region.id == "reg_1"
    assert cart.id == "cart_1"
    assert updated.items[0].quantity == 2
    assert ("POST", "/store/carts/cart_1/line-items", b'{"variant_id":"variant_1","quantity":2}') in calls
```

- [ ] Write failing tests for missing publishable key behavior:

```python
@pytest.mark.asyncio
async def test_store_client_requires_publishable_key_before_live_store_calls():
    from services.medusa_store import MedusaStoreConfigurationError

    client = MedusaStoreClient(Settings(medusa_backend_url="http://medusa.test"))

    with pytest.raises(MedusaStoreConfigurationError, match="MEDUSA_PUBLISHABLE_API_KEY"):
        await client.list_products()
```

- [ ] Run RED:

```powershell
cd examples/medusa-agent/backend
python -m pytest tests/test_slice3_medusa_store.py -q
```

Expected: fail because `MedusaStoreClient` does not exist.

## Task 2: Store Adapter Implementation

**Files:**

- Create: `examples/medusa-agent/backend/services/medusa_store.py`

- [ ] Implement typed models and client:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from core.config import Settings


@dataclass(frozen=True)
class StoreVariant:
    id: str
    title: str
    options: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class StoreProduct:
    id: str
    title: str
    description: str | None = None
    thumbnail: str | None = None
    variants: list[StoreVariant] = field(default_factory=list)


@dataclass(frozen=True)
class StoreRegion:
    id: str
    currency_code: str | None = None


@dataclass(frozen=True)
class StoreCartItem:
    id: str
    title: str | None = None
    quantity: int = 0
    variant_id: str | None = None


@dataclass(frozen=True)
class StoreCart:
    id: str
    items: list[StoreCartItem] = field(default_factory=list)


class MedusaStoreConfigurationError(RuntimeError):
    pass


class MedusaStoreClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self.transport = transport

    def _headers(self) -> dict[str, str]:
        if not self.settings.medusa_publishable_api_key:
            raise MedusaStoreConfigurationError("MEDUSA_PUBLISHABLE_API_KEY is required for Store API calls.")
        return {
            "Accept": "application/json",
            "x-publishable-api-key": self.settings.medusa_publishable_api_key,
        }

    def _base_url(self) -> str:
        return self.settings.medusa_backend_url.rstrip("/")

    async def list_products(self, limit: int = 12) -> list[StoreProduct]:
        async with httpx.AsyncClient(transport=self.transport, timeout=5.0, headers=self._headers()) as client:
            response = await client.get(f"{self._base_url()}/store/products", params={"limit": limit})
            response.raise_for_status()
        return [_parse_product(product) for product in response.json().get("products", [])]

    async def get_product(self, product_id: str) -> StoreProduct:
        async with httpx.AsyncClient(transport=self.transport, timeout=5.0, headers=self._headers()) as client:
            response = await client.get(f"{self._base_url()}/store/products/{product_id}")
            response.raise_for_status()
        return _parse_product(response.json()["product"])

    async def first_region(self) -> StoreRegion:
        async with httpx.AsyncClient(transport=self.transport, timeout=5.0, headers=self._headers()) as client:
            response = await client.get(f"{self._base_url()}/store/regions")
            response.raise_for_status()
        region = response.json().get("regions", [])[0]
        return StoreRegion(id=region["id"], currency_code=region.get("currency_code"))

    async def create_cart(self, region_id: str) -> StoreCart:
        async with httpx.AsyncClient(transport=self.transport, timeout=5.0, headers=self._headers()) as client:
            response = await client.post(f"{self._base_url()}/store/carts", json={"region_id": region_id})
            response.raise_for_status()
        return _parse_cart(response.json()["cart"])

    async def add_line_item(self, cart_id: str, variant_id: str, quantity: int) -> StoreCart:
        async with httpx.AsyncClient(transport=self.transport, timeout=5.0, headers=self._headers()) as client:
            response = await client.post(
                f"{self._base_url()}/store/carts/{cart_id}/line-items",
                json={"variant_id": variant_id, "quantity": quantity},
            )
            response.raise_for_status()
        return _parse_cart(response.json()["cart"])


def _parse_product(raw: dict[str, Any]) -> StoreProduct:
    return StoreProduct(
        id=raw["id"],
        title=raw.get("title") or "Untitled product",
        description=raw.get("description"),
        thumbnail=raw.get("thumbnail"),
        variants=[
            StoreVariant(
                id=variant["id"],
                title=variant.get("title") or "Default",
                options=[str(option.get("value")) for option in variant.get("options", []) if option.get("value")],
            )
            for variant in raw.get("variants", [])
        ],
    )


def _parse_cart(raw: dict[str, Any]) -> StoreCart:
    return StoreCart(
        id=raw["id"],
        items=[
            StoreCartItem(
                id=item["id"],
                title=item.get("title"),
                quantity=int(item.get("quantity") or 0),
                variant_id=item.get("variant_id"),
            )
            for item in raw.get("items", [])
        ],
    )
```

- [ ] Run GREEN:

```powershell
python -m pytest tests/test_slice3_medusa_store.py -q
```

Expected: store adapter tests pass.

## Task 3: Opaque Refs And Commerce State

**Files:**

- Create: `examples/medusa-agent/backend/services/commerce_refs.py`
- Create: `examples/medusa-agent/backend/services/commerce_state.py`
- Modify: `examples/medusa-agent/backend/tests/test_slice3_medusa_store.py`

- [ ] Add failing opaque-ref tests:

```python
def test_opaque_refs_hide_private_medusa_ids():
    from services.commerce_refs import OpaqueRefStore

    refs = OpaqueRefStore(prefix="demo")
    public_ref = refs.remember("prod_123")

    assert public_ref.startswith("demo_")
    assert "prod_123" not in public_ref
    assert refs.resolve(public_ref) == "prod_123"
```

- [ ] Add failing per-session cart state tests:

```python
def test_commerce_state_tracks_selected_variant_without_raw_ids_in_snapshot():
    from services.commerce_state import CommerceStateStore

    store = CommerceStateStore()
    state = store.for_session("session-1")
    state.selected_product_ref = "product_opaque"
    state.selected_variant_ref = "variant_opaque"

    snapshot = state.public_snapshot()

    assert snapshot["selected_product_ref"] == "product_opaque"
    assert snapshot["selected_variant_ref"] == "variant_opaque"
    assert "prod_" not in str(snapshot)
    assert "variant_" not in str(snapshot)
```

- [ ] Implement minimal state stores:

```python
from __future__ import annotations

import uuid


class OpaqueRefStore:
    def __init__(self, prefix: str) -> None:
        self.prefix = prefix
        self._forward: dict[str, str] = {}
        self._reverse: dict[str, str] = {}

    def remember(self, private_id: str) -> str:
        if private_id in self._reverse:
            return self._reverse[private_id]
        public_ref = f"{self.prefix}_{uuid.uuid4().hex[:12]}"
        self._forward[public_ref] = private_id
        self._reverse[private_id] = public_ref
        return public_ref

    def resolve(self, public_ref: str) -> str:
        return self._forward[public_ref]
```

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CommerceSessionState:
    selected_product_ref: str | None = None
    selected_variant_ref: str | None = None
    cart_ref: str | None = None

    def public_snapshot(self) -> dict[str, str | None]:
        return {
            "selected_product_ref": self.selected_product_ref,
            "selected_variant_ref": self.selected_variant_ref,
            "cart_ref": self.cart_ref,
        }


class CommerceStateStore:
    def __init__(self) -> None:
        self._sessions: dict[str, CommerceSessionState] = {}

    def for_session(self, session_id: str) -> CommerceSessionState:
        return self._sessions.setdefault(session_id, CommerceSessionState())
```

- [ ] Run:

```powershell
python -m pytest tests/test_slice3_medusa_store.py -q
```

Expected: adapter and state tests pass.

## Task 4: RouteDeck Manifest And Runtime Contract Tests

**Files:**

- Modify: `examples/medusa-agent/backend/tests/test_slice3_routedeck_runtime.py`
- Modify: `examples/medusa-agent/backend/services/routedeck_manifest.py`
- Modify: `examples/medusa-agent/backend/services/routedeck_runtime.py`

- [ ] Write failing tests for Slice 3 manifest:

```python
def test_slice3_manifest_defines_browse_detail_and_cart_without_checkout(client):
    response = client.get("/api/routedeck/manifest")
    assert response.status_code == 200
    manifest = response.json()

    assert manifest["version"] == "medusa-agent-slice3"
    assert [node["id"] for node in manifest["nodes"]] == ["browse", "detail", "cart"]
    action_ids = [action["id"] for action in manifest["actions"]]
    assert action_ids == [
        "catalog.list",
        "catalog.open",
        "variant.select",
        "cart.create",
        "cart.add_item",
        "cart.view",
    ]
    assert "checkout" not in response.text.lower()
    assert "payment" not in response.text.lower()
    assert "shipping" not in response.text.lower()
    assert "admin" not in response.text.lower()
```

- [ ] Write failing tests for unavailable setup:

```python
def test_projection_has_no_product_operations_when_setup_is_not_ready(client):
    response = client.get("/api/routedeck/projection?session_id=offline-session")
    assert response.status_code == 200
    projection = response.json()

    assert projection["legal_operations"] == []
    assert projection["surfaces"]["active"]["variant"] == "setup_status"
    assert "products" not in projection["surfaces"]["active"]["props"]
```

- [ ] Write failing tests for ready product projection with mocked Medusa client:

```python
@pytest.mark.asyncio
async def test_ready_projection_exposes_sanitized_products(monkeypatch):
    from services.medusa_store import StoreProduct, StoreVariant
    from services.routedeck_runtime import MedusaRouteDeckRuntime
    from core.config import Settings

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
    runtime = MedusaRouteDeckRuntime(settings=Settings(medusa_publishable_api_key="pk_test"), store_client=FakeStoreClient())

    projection = await runtime.projection(context={"session_id": "s1"})
    payload = projection.model_dump(mode="json")

    assert [operation.id for operation in projection.legal_operations] == ["catalog.list", "catalog.open", "cart.view"]
    assert payload["surfaces"]["active"]["variant"] == "product_list"
    assert payload["surfaces"]["active"]["props"]["products"][0]["title"] == "Medusa T-Shirt"
    assert "prod_private" not in str(payload)
    assert "variant_private" not in str(payload)
```

- [ ] Run RED:

```powershell
python -m pytest tests/test_slice3_routedeck_runtime.py -q
```

Expected: fail until manifest/runtime are updated.

## Task 5: Runtime Implementation

**Files:**

- Modify: `examples/medusa-agent/backend/services/routedeck_manifest.py`
- Modify: `examples/medusa-agent/backend/services/routedeck_runtime.py`

- [ ] Update `SLICE2_MANIFEST` to `SLICE3_MANIFEST` and keep `SLICE2_MANIFEST = SLICE3_MANIFEST` as a compatibility alias only if older imports require it.
- [ ] Add nodes `browse`, `detail`, and `cart`.
- [ ] Add the six action specs from the operation contract.
- [ ] Update `MedusaRouteDeckRuntime.__init__` to accept optional `store_client`, `ref_store`, and `state_store` for tests.
- [ ] In `projection()`:
  - Probe setup.
  - If setup is not ready, return setup status and no legal operations.
  - If setup is ready, list products through `MedusaStoreClient`.
  - Convert private IDs to opaque refs.
  - Return product list surface with sanitized products.
  - Return only legal operation objects appropriate for current state.
- [ ] In `dispatch()`:
  - Reject all unknown operation IDs.
  - Reject operations when setup is not ready.
  - Implement `catalog.list`, `catalog.open`, `variant.select`, `cart.create`, `cart.add_item`, and `cart.view`.
  - Return `RouteDeckDispatchResult` with new runtime state and no private IDs in messages or metadata.
  - Increment projection version after accepted dispatch.

Use these operation result messages:

```python
{
    "catalog.list": "Products are ready to browse.",
    "catalog.open": "Product details are ready.",
    "variant.select": "Variant selected.",
    "cart.create": "Cart ready.",
    "cart.add_item": "Added to cart.",
    "cart.view": "Cart summary ready.",
}
```

- [ ] Run:

```powershell
python -m pytest tests/test_slice3_routedeck_runtime.py -q
```

Expected: runtime tests pass.

## Task 6: RouteDeck Prompt And Agent Tools

**Files:**

- Modify: `examples/medusa-agent/backend/services/routedeck_prompt.py`
- Create: `examples/medusa-agent/backend/services/agent_tools.py`
- Modify: `examples/medusa-agent/backend/services/graph_builder.py`
- Modify: `examples/medusa-agent/backend/services/chat_service.py`
- Modify: `examples/medusa-agent/backend/tests/test_slice1_chat.py`
- Create or modify: `examples/medusa-agent/backend/tests/test_slice3_agent_tools.py`

- [ ] Write failing tests that RouteDeck prompt describes operation labels without leaking IDs:

```python
@pytest.mark.asyncio
async def test_routedeck_prompt_names_capabilities_without_operation_ids(monkeypatch):
    from routedeck_core import RouteDeckLocation, RouteDeckNavigationState, RouteDeckOperation, RouteDeckProjection
    from core.config import Settings
    from services import routedeck_prompt

    projection = RouteDeckProjection(
        current_context="browse",
        graph_node="browse",
        legal_operations=[
            RouteDeckOperation(id="catalog.list", label="Browse products", safety_class="read_external"),
            RouteDeckOperation(id="cart.add_item", label="Add selected item to cart", safety_class="write_external"),
        ],
        surfaces={},
        navigation=RouteDeckNavigationState(current=RouteDeckLocation(node_id="browse")),
    )

    class FakeRuntime:
        def __init__(self, settings):
            pass

        async def projection(self, context=None):
            return projection

    monkeypatch.setattr(routedeck_prompt, "MedusaRouteDeckRuntime", FakeRuntime)

    prompt = await routedeck_prompt.build_routedeck_system_prompt(Settings(openai_api_key="test-key"), session_id="s1")

    assert "Browse products" in prompt
    assert "Add selected item to cart" in prompt
    assert "catalog.list" not in prompt
    assert "cart.add_item" not in prompt
```

- [ ] Write failing tests that agent tools dispatch through runtime:

```python
@pytest.mark.asyncio
async def test_agent_tool_calls_routedeck_dispatch(monkeypatch):
    from routedeck_core import (
        RouteDeckDispatchResult,
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

    assert calls == [("catalog.list", {}, {"session_id": "s1", "source": "agent_tool"})]
    assert "Products are ready" in result
```

- [ ] Implement `agent_tools.py` with tool names:
  - `browse_products`
  - `open_product`
  - `select_variant`
  - `add_selected_variant_to_cart`
  - `view_cart`
- [ ] Each tool must call `MedusaRouteDeckRuntime.dispatch()` with a `RouteDeckDispatchInput`.
- [ ] Tools must return product-language summaries only. They must not return operation IDs, raw Medusa IDs, endpoint paths, or dispatch traces.
- [ ] Update `graph_builder.py` to bind tools with `llm.bind_tools(...)`.
- [ ] Keep `ChatService` responsible for injecting the dynamic RouteDeck prompt and session ID.
- [ ] Run:

```powershell
python -m pytest tests/test_slice1_chat.py tests/test_slice3_agent_tools.py -q
```

Expected: graph and tool tests pass.

## Task 7: Routes And Query Context

**Files:**

- Modify: `examples/medusa-agent/backend/routes/routedeck.py`
- Modify: `examples/medusa-agent/backend/routes/state.py`
- Modify: `examples/medusa-agent/backend/tests/test_slice3_routedeck_runtime.py`

- [ ] Add `session_id` query support for projection, snapshot, inspect, and stream:

```python
@router.get("/api/routedeck/projection")
async def projection(session_id: str = "default"):
    return (await runtime.projection({"session_id": session_id})).model_dump(mode="json")


@router.get("/api/routedeck/snapshot")
async def snapshot(session_id: str = "default"):
    return (await runtime.snapshot({"session_id": session_id})).model_dump(mode="json")


@router.post("/api/routedeck/inspect")
async def inspect(body: dict | None = None, session_id: str = "default"):
    context = {"session_id": session_id}
    return {"introspection": (await runtime.inspect(body or {}, context=context)).model_dump(mode="json")}


@router.get("/api/routedeck/stream")
async def stream(session_id: str = "default"):
    async def generate():
        async for event in runtime.stream({"session_id": session_id}):
            payload = json.dumps(event.model_dump(mode="json"))
            yield f"event: {event.event_type}\ndata: {payload}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

- [ ] Update dispatch route to merge `body.context` and fallback `session_id`:

```python
@router.post("/api/routedeck/dispatch")
async def dispatch(body: RouteDeckDispatchInput):
    context = {"session_id": "default", **body.context}
    request = body.model_copy(update={"context": context})
    try:
        return (await runtime.dispatch(request, context=context)).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
```

- [ ] Add tests:

```python
def test_projection_accepts_session_id_without_exposing_it_in_ui_props(client):
    response = client.get("/api/routedeck/projection?session_id=session-abc")
    assert response.status_code == 200
    assert "session-abc" not in response.text


def test_snapshot_inspect_and_stream_accept_session_id_without_public_echo(client):
    snapshot = client.get("/api/routedeck/snapshot?session_id=session-abc")
    inspect = client.post("/api/routedeck/inspect?session_id=session-abc", json={"surface": "active"})
    stream = client.get("/api/routedeck/stream?session_id=session-abc")

    assert snapshot.status_code == 200
    assert inspect.status_code == 200
    assert stream.status_code == 200
    assert "session-abc" not in snapshot.text
    assert "session-abc" not in inspect.text
    assert "session-abc" not in stream.text


def test_dispatch_merges_context_and_preserves_session_id(client):
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
```

- [ ] Run:

```powershell
python -m pytest tests/test_slice3_routedeck_runtime.py -q
```

Expected: route tests pass.

## Task 8: Frontend Projection Hook And Product UI

**Files:**

- Create: `examples/medusa-agent/frontend/src/hooks/useRouteDeckProjection.ts`
- Modify: `examples/medusa-agent/frontend/src/App.tsx`
- Modify: `examples/medusa-agent/frontend/src/styles.css`
- Modify: `examples/medusa-agent/frontend/src/App.test.tsx`

- [ ] Write failing frontend tests for chat-first product browse:

```tsx
test("renders product list from projection without RouteDeck internals", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url.includes("/api/routedeck/projection")) {
      return new Response(JSON.stringify({
        graph_node: "browse",
        legal_operations: [{ id: "catalog.open", label: "View product" }],
        surfaces: {
          active: {
            variant: "product_list",
            props: {
              products: [
                { product_ref: "p_ref", title: "Medusa T-Shirt", thumbnail: "https://example.test/shirt.png", variants: [{ variant_ref: "v_ref", title: "M" }] },
              ],
            },
          },
        },
        navigation: { current: { node_id: "browse" }, back_stack: [], forward_stack: [] },
      }))
    }
    return new Response("{}", { status: 404 })
  }))

  render(<App />)

  expect(screen.getByRole("textbox", { name: /message/i })).toBeInTheDocument()
  expect(await screen.findByText("Medusa T-Shirt")).toBeInTheDocument()
  expect(screen.queryByText(/catalog.open|p_ref|v_ref|routedeck|dispatch|graph_node/i)).not.toBeInTheDocument()
})
```

- [ ] Write failing tests for UI dispatch:

```tsx
test("view product click dispatches through generic RouteDeck endpoint", async () => {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.includes("/api/routedeck/projection")) {
      return new Response(JSON.stringify({
        graph_node: "browse",
        legal_operations: [{ id: "catalog.open", label: "View product" }],
        surfaces: { active: { variant: "product_list", props: { products: [{ product_ref: "p_ref", title: "Medusa T-Shirt" }] } } },
        navigation: { current: { node_id: "browse" }, back_stack: [], forward_stack: [] },
      }))
    }
    if (url === "/api/routedeck/dispatch") {
      expect(JSON.parse(String(init?.body))).toMatchObject({
        operation_id: "catalog.open",
        args: { product_ref: "p_ref" },
      })
      return new Response(JSON.stringify({ accepted: true }))
    }
    return new Response("{}", { status: 404 })
  })
  vi.stubGlobal("fetch", fetchMock)

  render(<App />)
  fireEvent.click(await screen.findByRole("button", { name: /view medusa t-shirt/i }))

  expect(fetchMock).toHaveBeenCalledWith("/api/routedeck/dispatch", expect.objectContaining({ method: "POST" }))
})
```

- [ ] Implement `useRouteDeckProjection.ts`:
  - maintain stable `session_id` in `window.localStorage`.
  - fetch `/api/routedeck/projection?session_id=...`.
  - expose `dispatch(operation_id, args)`.
  - refetch projection after accepted dispatch.
  - keep opaque refs in component state and dispatch payloads only; never render them as visible text or transcript text.
- [ ] Render:
  - setup status when setup is not ready.
  - compact product list when `variant === "product_list"`.
  - product detail and variant choices when `variant === "product_detail"`.
  - cart summary when cart props exist.
- [ ] Do not render operation IDs, graph node IDs, endpoint paths, diagnostics, dispatch traces, opaque refs, checkout/payment/shipping/admin text, or hidden Medusa IDs.
- [ ] Run:

```powershell
cd examples/medusa-agent/frontend
npm test
```

Expected: frontend tests pass.

## Task 9: Documentation And Guard Updates

**Files:**

- Modify: `examples/medusa-agent/README.md`
- Modify: `docs/medusa-agent-reference-app.md`
- Modify: `tests/test_medusa_reference_slice0.py`

- [ ] Update README title to `Medusa Agent Slices 1-3`.
- [ ] Add Slice 3 sections:
  - Local/demo Medusa Store API requirement.
  - Publishable key header requirement.
  - Product browse/detail/cart scope.
  - Private ID hiding rule.
  - No checkout/payment/shipping/admin/Docker.
  - Agent uses RouteDeck prompt context and tools; no phrase router.
- [ ] Link this plan under Slice 3 in `docs/medusa-agent-reference-app.md`:

```markdown
Implementation plan:
`docs/superpowers/plans/2026-06-03-medusa-agent-slice3.md`.
```

- [ ] Update root guard:

```python
def test_medusa_slice3_allows_browse_and_cart_but_not_checkout_admin_or_product_routes():
    text = _combined_text("examples/medusa-agent/backend", "examples/medusa-agent/frontend/src")
    assert "/api/routedeck/projection" in text
    assert "/api/routedeck/dispatch" in text
    assert "/api/routedeck/medusa" not in text.lower()
    assert "catalog.list" in text
    assert "cart.add_item" in text
    for banned in ["fulfillment", "admin mutation", "@medusajs/"]:
        assert banned not in text.lower()
```

Do not globally ban words like `checkout`, `payment`, or `shipping` in docs or
tests, because Slice 3 docs should explicitly name them as non-goals. Instead,
ban future-scope commerce language from public UI and agent prompt text:

```python
def test_medusa_slice3_public_surfaces_do_not_advertise_future_scope():
    public_text = _combined_text(
        "examples/medusa-agent/frontend/src",
        "examples/medusa-agent/backend/services/routedeck_prompt.py",
    ).lower()
    for banned in ["checkout", "payment", "shipping", "fulfillment", "admin"]:
        assert banned not in public_text
```

- [ ] Add an ID leak guard:

```python
def test_medusa_slice3_public_ui_and_chat_do_not_expose_private_ids():
    public_text = _combined_text("examples/medusa-agent/frontend/src", "examples/medusa-agent/backend/services/routedeck_prompt.py")
    for private_prefix in ["prod_", "variant_", "cart_", "line_"]:
        assert private_prefix not in public_text
```

- [ ] Run:

```powershell
cd agent-lab-powered-projects/routedeck
python -m pytest tests -q
```

Expected: root tests pass.

## Task 10: Full Verification

**Files:** no code changes.

- [ ] Backend tests:

```powershell
cd examples/medusa-agent/backend
python -m pytest tests -q
```

- [ ] Frontend tests:

```powershell
cd examples/medusa-agent/frontend
npm test
```

- [ ] Root tests:

```powershell
cd agent-lab-powered-projects/routedeck
python -m pytest tests -q
```

- [ ] Live smoke with Medusa unavailable:
  - Start backend on `127.0.0.1:8098`.
  - Start frontend on `127.0.0.1:5198`.
  - Confirm setup shows not ready.
  - Ask `show me products`.
  - Confirm the agent does not list invented products and explains local demo Medusa is not connected.
  - Confirm `/api/routedeck/projection` has `legal_operations: []`.

- [ ] Live smoke with local/demo Medusa available:
  - Start local/demo Medusa outside this slice if already available.
  - Set `MEDUSA_BACKEND_URL` and `MEDUSA_PUBLISHABLE_API_KEY`.
  - Restart backend.
  - Confirm `/api/medusa-agent/state` has `setup.ready: true`.
  - Confirm `/api/routedeck/projection` exposes product list with no private IDs.
  - In UI, view a product, select a variant, add one item to cart.
  - In chat, ask to browse products and add a selected item; confirm the agent uses RouteDeck tools and does not show operation IDs or raw Medusa IDs.
  - Confirm no checkout, payment, shipping, or admin UI appears.

## Self-Review

- Spec coverage: covers product browse, product detail, variant selection, cart create/add/view, shared UI/agent dispatch, private ID hiding, and RouteDeck prompt/tool awareness.
- Deliberate gaps: checkout, payment, shipping, fulfillment, admin mutation, Docker, seeded reset, and order completion remain excluded.
- Drift checks: no fake product data, no phrase router, no RouteDeck internals in public chat/UI, no product-specific RouteDeck routes, and no future operation catalogs beyond Slice 3.
- Type consistency: uses existing `routedeck_core` names: `RouteDeckManifest`, `RouteDeckActionSpec`, `RouteDeckOperation`, `RouteDeckSurface`, `RouteDeckRuntimeState`, `RouteDeckDispatchInput`, `RouteDeckDispatchResult`, `RouteDeckIntrospection`, and `RouteDeckEvent`.
