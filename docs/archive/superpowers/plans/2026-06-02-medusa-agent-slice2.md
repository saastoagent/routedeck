# Medusa Agent Slice 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the Medusa example to local/demo Medusa setup status and introduce a separate generic RouteDeck API plane without adding cart, checkout, admin mutation, or product browse behavior.

**Architecture:** Slice 2 keeps chat under `/api/medusa-agent/*` and adds generic RouteDeck runtime endpoints under `/api/routedeck/*` as framework evidence, not as the product experience. Medusa-specific setup checks live in app-owned adapter/services, while RouteDeck payloads use `routedeck_core` contracts for manifest, projection, runtime state, guarded dispatch validation, inspect output, and events. The UI remains chat-first, with passive setup readiness only; operation lists, command buttons, dispatch traces, and diagnostics stay out of the default product UI.

**Tech Stack:** FastAPI, pytest, httpx, RouteDeck core Python contracts, React, Vite, Vitest, Testing Library, local/demo Medusa HTTP health/setup probes.

---

## Scope

Build only Slice 2:

- Keep `POST /api/medusa-agent/agent/stream` as the product-owned chat endpoint.
- Add generic RouteDeck endpoints:
  - `GET /api/routedeck/manifest`
  - `GET /api/routedeck/snapshot`
  - `GET /api/routedeck/projection`
  - `POST /api/routedeck/dispatch`
  - `POST /api/routedeck/inspect`
  - `GET /api/routedeck/stream`
- Add app-owned Medusa setup status:
  - `GET /api/medusa-agent/state`
- Connect only to local/demo Medusa setup/health/config status.
- Show passive product setup readiness only.
- Keep operation lists, blocked future actions, dispatch traces, and diagnostics out of the default product UI.
- Treat `/api/routedeck/dispatch`, `/api/routedeck/inspect`, and `/api/routedeck/stream` as generic framework contract endpoints only; they must not power chat behavior or product-facing controls in this slice.
- Keep RouteDeck payloads generic; no `/api/routedeck/medusa/*`.
- Do not add product browse, product detail, variant selection, cart, checkout, payment, shipping, fulfillment, admin mutation, Docker, or seeded catalog reset. Those begin in later slices.

## File Structure

- Modify `examples/medusa-agent/backend/core/config.py`: add `MEDUSA_BACKEND_URL`, `MEDUSA_STOREFRONT_URL`, and optional `MEDUSA_PUBLISHABLE_API_KEY` env settings loaded from backend `.env`.
- Create `examples/medusa-agent/backend/services/medusa_setup.py`: app-owned Medusa connection probe and setup status model.
- Create `examples/medusa-agent/backend/services/routedeck_manifest.py`: static generic RouteDeck manifest for Slice 2 setup/projection.
- Create `examples/medusa-agent/backend/services/routedeck_runtime.py`: `MedusaRouteDeckRuntime` that builds snapshot/projection/inspect/stream from setup state and rejects dispatch execution in Slice 2.
- Create `examples/medusa-agent/backend/routes/state.py`: `GET /api/medusa-agent/state`.
- Create `examples/medusa-agent/backend/routes/routedeck.py`: generic RouteDeck API routes.
- Modify `examples/medusa-agent/backend/main.py`: register state and RouteDeck routers.
- Create `examples/medusa-agent/backend/tests/test_slice2_routedeck.py`: backend contract tests for API split, setup state, projection, guarded dispatch rejection, inspect, stream, and forbidden surfaces.
- Modify `examples/medusa-agent/backend/tests/test_slice1_chat.py`: keep no-fallback and chat tests unchanged.
- Modify `examples/medusa-agent/frontend/src/hooks/useRouteDeckStatus.ts`: new hook for setup state and RouteDeck projection.
- Modify `examples/medusa-agent/frontend/src/App.tsx`: add compact setup/status surface below or beside chat without turning the first screen into a dashboard.
- Modify `examples/medusa-agent/frontend/src/App.test.tsx`: test setup/status rendering and absence of later-slice UI.
- Modify `examples/medusa-agent/README.md`: add Slice 2 env vars, local/demo Medusa setup status command, and non-goals.
- Modify `tests/test_medusa_reference_slice0.py`: rename or update the Slice 1 guard so generic `/api/routedeck/*` is allowed only when it is product-neutral, while product-specific RouteDeck routes and later-slice commerce code stay banned.

## RouteDeck Contract

Initial Slice 2 manifest:

```python
from routedeck_core import RouteDeckManifest, RouteDeckNodeSpec

SLICE2_MANIFEST = RouteDeckManifest(
    version="medusa-agent-slice2",
    nodes=[
        RouteDeckNodeSpec(
            id="setup",
            label="Setup",
            lane="setup",
            description="Check local demo Medusa connectivity.",
            allowed_actions=[],
            allowed_surfaces={"active": ["setup_status"]},
            default_surfaces={"active": "setup_status"},
        )
    ],
    edges=[],
    actions=[],
)
```

Allowed Slice 2 RouteDeck operations:

- None. Setup refresh is app-owned state retrieval, not a RouteDeck dispatch operation.

Blocked or absent operations:

- Any product or commerce operation, without enumerating future command IDs in the runtime output.
- Any surface-switching operation in the default product UI.
- Any product-specific RouteDeck route such as `/api/routedeck/medusa/*`.

## Task 1: Backend Slice 2 Contract Tests

**Files:**

- Create: `examples/medusa-agent/backend/tests/test_slice2_routedeck.py`

- [ ] Write failing tests for generic RouteDeck endpoints:

```python
def test_routedeck_manifest_is_generic_and_setup_scoped(client):
    response = client.get("/api/routedeck/manifest")
    assert response.status_code == 200
    manifest = response.json()
    assert manifest["version"] == "medusa-agent-slice2"
    assert [node["id"] for node in manifest["nodes"]] == ["setup"]
    assert "/api/routedeck/medusa" not in response.text
    assert "checkout" not in response.text.lower()
    assert "cart" not in response.text.lower()


def test_projection_exposes_setup_status_and_blocks_unavailable_connection(client):
    response = client.get("/api/routedeck/projection")
    assert response.status_code == 200
    projection = response.json()
    assert projection["graph_node"] == "setup"
    assert "active" in projection["surfaces"]
    assert projection["surfaces"]["active"]["variant"] == "setup_status"
    assert projection["legal_operations"] == []
    assert "diagnostics" not in projection["surfaces"]["active"]
```

- [ ] Write failing tests for app-owned Medusa state:

```python
def test_medusa_agent_state_reports_setup_not_commerce_state(client):
    response = client.get("/api/medusa-agent/state")
    assert response.status_code == 200
    state = response.json()
    assert set(state) >= {"setup", "connections"}
    assert "cart" not in state
    assert "checkout" not in state
```

- [ ] Write failing tests for guarded dispatch and dev-only inspection:

```python
def test_dispatch_rejects_all_operation_execution_in_slice2(client):
    response = client.post("/api/routedeck/dispatch", json={"operation_id": "medusa.setup.refresh", "args": {}})
    assert response.status_code == 400
    assert response.json()["detail"] == "No RouteDeck dispatchable operations are legal in Slice 2."
```

- [ ] Write failing tests for inspect and stream:

```python
def test_inspect_returns_framework_guard_without_future_command_catalog(client):
    response = client.post("/api/routedeck/inspect", json={})
    assert response.status_code == 200
    body = response.json()
    assert "introspection" in body
    assert "guard_explanations" in body["introspection"]
    assert body["introspection"]["legal_operations"] == []
    assert body["introspection"]["blocked_operations"] == []
    assert all("id" not in blocked for blocked in body["introspection"]["blocked_operations"])


def test_routedeck_stream_is_sse_projection_update(client):
    with client.stream("GET", "/api/routedeck/stream") as response:
        assert response.status_code == 200
        first = next(response.iter_text())
    assert "event: projection_update" in first
```

- [ ] Run RED:

```powershell
cd examples/medusa-agent/backend
python -m pytest tests/test_slice2_routedeck.py -q
```

Expected: fail because routes/services do not exist.

## Task 2: Medusa Setup Service

**Files:**

- Modify: `examples/medusa-agent/backend/core/config.py`
- Create: `examples/medusa-agent/backend/services/medusa_setup.py`

- [ ] Add settings:

```python
@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None = None
    medusa_agent_model: str = "gpt-5-mini"
    medusa_backend_url: str = "http://127.0.0.1:9000"
    medusa_storefront_url: str = "http://127.0.0.1:3007"
    medusa_publishable_api_key: str | None = None
    keepalive_interval: float = 15.0
    model_timeout_seconds: float = 30.0
```

- [ ] Implement setup probe:

```python
from dataclasses import dataclass

import httpx

from core.config import Settings


@dataclass(frozen=True)
class ConnectionStatus:
    name: str
    url: str
    ok: bool
    status_code: int | None = None
    error: str | None = None


async def probe_medusa_setup(settings: Settings, timeout: float = 2.0) -> dict:
    async with httpx.AsyncClient(timeout=timeout) as client:
        backend = await _probe(client, "backend", f"{settings.medusa_backend_url.rstrip('/')}/health")
        storefront = await _probe(client, "storefront", settings.medusa_storefront_url)
    ready = backend.ok and storefront.ok
    return {
        "setup": {"ready": ready, "mode": "local-demo"},
        "connections": [backend.__dict__, storefront.__dict__],
    }


async def _probe(client: httpx.AsyncClient, name: str, url: str) -> ConnectionStatus:
    try:
        response = await client.get(url)
        return ConnectionStatus(name=name, url=url, ok=response.status_code < 500, status_code=response.status_code)
    except httpx.HTTPError as exc:
        return ConnectionStatus(name=name, url=url, ok=False, error=type(exc).__name__)
```

- [ ] Run GREEN for setup service tests:

```powershell
python -m pytest tests/test_slice2_routedeck.py -q
```

Expected: remaining failures are route/runtime-related.

## Task 3: RouteDeck Runtime And Routes

**Files:**

- Create: `examples/medusa-agent/backend/services/routedeck_manifest.py`
- Create: `examples/medusa-agent/backend/services/routedeck_runtime.py`
- Create: `examples/medusa-agent/backend/routes/routedeck.py`
- Modify: `examples/medusa-agent/backend/main.py`

- [ ] Implement `routedeck_manifest.py` with `SLICE2_MANIFEST` exactly as shown in the RouteDeck Contract section.

- [ ] Implement `MedusaRouteDeckRuntime`:

```python
from collections.abc import AsyncIterator

from routedeck_core import (
    RouteDeckDispatchInput,
    RouteDeckDispatchResult,
    RouteDeckEvent,
    RouteDeckIntrospection,
    RouteDeckRuntimeState,
    RouteDeckSurface,
    build_projection,
)

from core.config import Settings
from services.medusa_setup import probe_medusa_setup
from services.routedeck_manifest import SLICE2_MANIFEST


class MedusaRouteDeckRuntime:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.from_env()
        self.projection_version = 1

    async def projection(self, context: dict | None = None):
        setup_state = await probe_medusa_setup(self.settings)
        return build_projection(
            SLICE2_MANIFEST,
            current_node="setup",
            operations=[],
            surfaces=[
                RouteDeckSurface(
                    name="active",
                    surface_id="setup.setup_status",
                    component="MedusaSetupPanel",
                    variant="setup_status",
                    role="active",
                    surface_kind="peer",
                    props=setup_state,
                )
            ],
            projection_version=self.projection_version,
            diagnostics={"setup": setup_state},
        )

    async def snapshot(self, context: dict | None = None) -> RouteDeckRuntimeState:
        projection = await self.projection(context)
        return RouteDeckRuntimeState(
            projection=projection,
            status="idle",
            graph_state={"node": "setup"},
            diagnostics=projection.diagnostics,
        )

    async def dispatch(self, request: RouteDeckDispatchInput, context: dict | None = None) -> RouteDeckDispatchResult:
        raise ValueError("No RouteDeck dispatchable operations are legal in Slice 2.")

    async def inspect(self, query: dict | None = None, context: dict | None = None) -> RouteDeckIntrospection:
        projection = await self.projection(context)
        return RouteDeckIntrospection(
            current_node="setup",
            legal_operations=[],
            blocked_operations=[],
            guard_explanations=[
                "Slice 2 exposes setup projection only.",
                "Product and commerce actions are outside this slice.",
            ],
            surfaces={key: surface.model_dump(mode="json") for key, surface in projection.surfaces.items()},
            diagnostics=projection.diagnostics,
        )

    async def stream(self, context: dict | None = None) -> AsyncIterator[RouteDeckEvent]:
        state = await self.snapshot(context)
        yield RouteDeckEvent(
            event_type="projection_update",
            projection_version=state.projection.projection_version,
            payload={"projection": state.projection.model_dump(mode="json"), "status": state.status},
        )
```

- [ ] Implement `routes/routedeck.py`:

```python
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from routedeck_core import RouteDeckDispatchInput

from services.routedeck_manifest import SLICE2_MANIFEST
from services.routedeck_runtime import MedusaRouteDeckRuntime

router = APIRouter(tags=["routedeck"])
runtime = MedusaRouteDeckRuntime()


@router.get("/api/routedeck/manifest")
async def manifest():
    return SLICE2_MANIFEST.model_dump(mode="json", by_alias=True)


@router.get("/api/routedeck/snapshot")
async def snapshot():
    return (await runtime.snapshot()).model_dump(mode="json")


@router.get("/api/routedeck/projection")
async def projection():
    return (await runtime.projection()).model_dump(mode="json")


@router.post("/api/routedeck/dispatch")
async def dispatch(body: RouteDeckDispatchInput):
    try:
        return (await runtime.dispatch(body)).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/routedeck/inspect")
async def inspect(body: dict | None = None):
    return {"introspection": (await runtime.inspect(body or {})).model_dump(mode="json")}


@router.get("/api/routedeck/stream")
async def stream():
    async def generate():
        async for event in runtime.stream():
            yield f"event: {event.event_type}\ndata: {json.dumps(event.model_dump(mode='json'))}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

- [ ] Register the router in `main.py`:

```python
from routes.routedeck import router as routedeck_router

app.include_router(routedeck_router)
```

- [ ] Run GREEN:

```powershell
python -m pytest tests/test_slice2_routedeck.py -q
```

Expected: backend Slice 2 tests pass.

## Task 4: App-Owned State Endpoint

**Files:**

- Create: `examples/medusa-agent/backend/routes/state.py`
- Modify: `examples/medusa-agent/backend/main.py`

- [ ] Implement state route:

```python
from fastapi import APIRouter

from core.config import Settings
from services.medusa_setup import probe_medusa_setup

router = APIRouter(tags=["medusa-agent-state"])


@router.get("/api/medusa-agent/state")
async def state():
    return await probe_medusa_setup(Settings.from_env())
```

- [ ] Register the router in `main.py`:

```python
from routes.state import router as state_router

app.include_router(state_router)
```

- [ ] Run:

```powershell
python -m pytest tests/test_slice2_routedeck.py -q
```

Expected: app-owned state tests pass.

## Task 5: Frontend Setup/Projection UI

**Files:**

- Create: `examples/medusa-agent/frontend/src/hooks/useRouteDeckStatus.ts`
- Modify: `examples/medusa-agent/frontend/src/App.tsx`
- Modify: `examples/medusa-agent/frontend/src/styles.css`
- Modify: `examples/medusa-agent/frontend/src/App.test.tsx`

- [ ] Write failing frontend tests:

```tsx
test("renders setup status without replacing the chat-first screen", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url.endsWith("/api/routedeck/projection")) {
      return new Response(JSON.stringify({
        graph_node: "setup",
        legal_operations: [],
        surfaces: { active: { variant: "setup_status", props: { setup: { ready: false } } } },
        navigation: { current: { node_id: "setup" }, back_stack: [], forward_stack: [] },
      }))
    }
    return new Response("{}", { status: 404 })
  }))

  render(<App />)

  expect(screen.getByRole("textbox", { name: /message/i })).toBeInTheDocument()
  expect(await screen.findByText(/setup/i)).toBeInTheDocument()
  expect(screen.queryByRole("button", { name: /refresh|switch|dispatch/i })).not.toBeInTheDocument()
  expect(screen.queryByText(/checkout|cart|payment|admin/i)).not.toBeInTheDocument()
})
```

- [ ] Implement `useRouteDeckStatus.ts`:

```ts
import { useEffect, useState } from "react";

export function useRouteDeckStatus() {
  const [projection, setProjection] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/routedeck/projection")
      .then((response) => {
        if (!response.ok) throw new Error(`RouteDeck status failed: ${response.status}`);
        return response.json();
      })
      .then((payload) => {
        if (!cancelled) setProjection(payload);
      })
      .catch((nextError) => {
        if (!cancelled) setError(nextError instanceof Error ? nextError.message : "Status failed");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { projection, error };
}
```

- [ ] Add a compact status section in `App.tsx` below the chat header or beside the message list:

```tsx
const { projection, error } = useRouteDeckStatus();
const activeSurface = projection?.surfaces?.active as { props?: { setup?: { ready?: boolean } } } | undefined;
const setupReady = Boolean(activeSurface?.props?.setup?.ready);
```

Render text labels such as `Setup`, `Connected`, and `Needs local demo Medusa`. Do not render operation ids, graph node ids, endpoint paths, dispatch controls, refresh buttons, or diagnostics by default.

- [ ] Run:

```powershell
cd examples/medusa-agent/frontend
npm test
```

Expected: frontend tests pass.

## Task 6: Scope Guards And Documentation

**Files:**

- Modify: `tests/test_medusa_reference_slice0.py`
- Modify: `examples/medusa-agent/README.md`
- Modify: `docs/medusa-agent-reference-app.md`

- [ ] Update guard test:

```python
def test_medusa_slice2_allows_generic_routedeck_api_but_not_product_specific_routes():
    text = _combined_text("examples/medusa-agent/backend", "examples/medusa-agent/frontend/src")
    assert "/api/routedeck/manifest" in text
    assert "/api/routedeck/medusa" not in text.lower()
    assert "routedeck_core" in text
    for banned in ["checkout", "payment", "shipping", "admin mutation", "@medusajs/"]:
        assert banned not in text.lower()
```

- [ ] Add README sections:
  - Slice 2 purpose.
  - Medusa local/demo env vars.
  - RouteDeck endpoints and what they return.
  - Explicit non-goals for product browse/cart/checkout/admin.
  - Reset remains process-local plus setup refresh only.

- [ ] Link this plan from `docs/medusa-agent-reference-app.md` under Slice 2:

```markdown
Implementation plan: `docs/superpowers/plans/2026-06-02-medusa-agent-slice2.md`.
```

## Verification

Run all commands from `agent-lab-powered-projects/routedeck` unless noted:

```powershell
python -m pytest examples/medusa-agent/backend/tests -q
cd examples/medusa-agent/frontend
npm test
cd ..\..\..
python -m pytest tests -q
```

Manual smoke:

- Start local/demo Medusa if available.
- Start backend on `127.0.0.1:8098`.
- Start frontend on `127.0.0.1:5198`.
- Open the chat app.
- Confirm chat remains the primary screen.
- Confirm setup status appears without RouteDeck internals in public chat.
- Confirm `GET /api/routedeck/manifest`, `GET /api/routedeck/projection`, and `POST /api/routedeck/inspect` return generic RouteDeck payloads.
- Confirm `/api/routedeck/medusa/*` is 404.
- Confirm no product browse, cart, checkout, payment, shipping, or admin mutation UI appears.

## Self-Review

- Spec coverage: covers Slice 2 setup connection, separate generic RouteDeck API plane, passive setup status, guarded dispatch rejection, and Medusa policy remaining app-owned.
- Deliberate gaps: product browse, cart, checkout, admin, Docker, seeded reset, and actual order/payment behavior are excluded for later slices.
- Type consistency: uses existing `routedeck_core` names: `RouteDeckManifest`, `RouteDeckSurface`, `RouteDeckRuntimeState`, `RouteDeckDispatchInput`, `RouteDeckDispatchResult`, `RouteDeckIntrospection`, and `RouteDeckEvent`.
