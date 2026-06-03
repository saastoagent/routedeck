# Medusa Agent Slices 1-3

This example is the first runnable Medusa reference-app line. Slice 1 proves a
normal app-owned commerce chat agent. Slice 2 adds passive setup readiness from
the separate generic RouteDeck API plane without turning the product UI into a
debugger or commerce workbench. Slice 3 adds Store API-backed product browse,
variant selection, and demo cart add behavior through shared RouteDeck dispatch.

## Scope

Implemented scope includes:

- FastAPI backend owned by this app.
- React chat UI as the first screen.
- True Server-Sent Events at `POST /api/medusa-agent/agent/stream`.
- Minimal LangGraph agent with default model `gpt-5-mini`.
- Explicit error event when `OPENAI_API_KEY` is not configured.
- Process-local conversation state with `conversation_id` mapped to
  `configurable.thread_id`.
- Passive setup readiness in the chat UI using the generic
  `GET /api/routedeck/projection` contract.
- Product browse/detail/cart surfaces derived from the generic RouteDeck
  projection.
- LangGraph tools and UI clicks dispatch through the same generic
  `POST /api/routedeck/dispatch` contract.
- Store API calls use the app-owned backend adapter and
  `MEDUSA_PUBLISHABLE_API_KEY`.
- Private Medusa IDs stay server-side behind opaque refs.

Slice 3 does not include checkout, payment, shipping, fulfillment, admin
mutation flows, seeded catalog reset, Docker, order completion, refund, cancel,
delete, or production data.

## RouteDeck Setup And Commerce Projection

Slice 2 connected only to local/demo Medusa setup status. Slice 3 keeps the
product screen chat-first, then adds compact product and cart surfaces when the
local/demo Store API is ready. The UI may show labels such as `Setup`,
`Connected`, `Needs local demo Medusa`, product names, variants, quantities, and
cart item names. It must not render operation IDs, graph node IDs, endpoint
paths, dispatch traces, route switching, diagnostics, blocked future actions, or
private Medusa IDs.

The generic RouteDeck plane is framework evidence only:

- `GET /api/routedeck/manifest` returns the Slice 3 RouteDeck manifest.
- `GET /api/routedeck/snapshot` returns generic runtime state.
- `GET /api/routedeck/projection` returns setup, product, detail, or cart
  projection payloads.
- `POST /api/routedeck/dispatch` accepts only the typed Slice 3 operations:
  `catalog.list`, `catalog.open`, `variant.select`, `cart.create`,
  `cart.add_item`, and `cart.view`.
- `POST /api/routedeck/inspect` returns framework introspection for development
  checks, not the default product UI.
- `GET /api/routedeck/stream` emits generic projection updates.

No product-specific RouteDeck route such as `/api/routedeck/medusa/*` is part of
this slice.

## Foundation-Agent Subset

This app keeps only the small foundation-agent shape needed for chat streaming:

- SSE frame helpers.
- FastAPI `StreamingResponse` route.
- Async stream orchestration.
- LangGraph commerce agent with RouteDeck-backed tools.
- XHR-based SSE parsing in React.

Auth, database persistence, document workflows, tool calls, citations, memory,
citations, memory, and upload flows are intentionally omitted.

## Slice 3 Store API Scope

Live browse/cart behavior requires local/demo Medusa plus:

```powershell
$env:MEDUSA_BACKEND_URL = "http://127.0.0.1:9000"
$env:MEDUSA_PUBLISHABLE_API_KEY = "..."
```

The backend calls only these Store API endpoints:

- `GET /store/products`
- `GET /store/products/{id}`
- `GET /store/regions`
- `POST /store/carts`
- `POST /store/carts/{id}/line-items`

If setup or the publishable key is unavailable, the app reports that local demo
Medusa is not connected for that capability. It must not invent product names,
prices, variants, inventory, availability, or cart state.

The agent learns available capability labels from RouteDeck prompt context and
uses RouteDeck tools. There is no phrase router, alias table, hardcoded product
catalog, or deterministic chat command path.

## Dependencies

Backend pins checked on 2026-05-28:

```text
fastapi==0.136.3
httpx==0.28.1
langchain-openai==1.2.2
langgraph==1.2.2
pytest==9.0.3
uvicorn==0.48.0
```

Frontend pins checked on 2026-05-28:

```text
@vitejs/plugin-react@6.0.2
react@19.2.6
react-dom@19.2.6
typescript@6.0.3
vite@8.0.14
@testing-library/jest-dom@6.9.1
@testing-library/react@16.3.2
jsdom@26.1.0
vitest@4.1.7
```

The pinned frontend stack requires Node `^20.19.0 || >=22.12.0`.

## Environment

```powershell
$env:OPENAI_API_KEY = "..."
$env:MEDUSA_AGENT_MODEL = "gpt-5-mini"
$env:MEDUSA_BACKEND_URL = "http://127.0.0.1:9000"
$env:MEDUSA_STOREFRONT_URL = "http://127.0.0.1:3007"
$env:MEDUSA_PUBLISHABLE_API_KEY = "..."
```

For this checkout, the backend also reads `examples/medusa-agent/backend/.env`.
That file is gitignored. When working inside `agent-core`, it can be populated
from the SaaStoAgent env by copying `STA_OPENAI_API_KEY` into `OPENAI_API_KEY`.

`OPENAI_API_KEY` is required for agent responses. Without it, the backend emits
an SSE `error` event with code `openai_api_key_missing`. Slice 1 intentionally
does not include fallback assistant text.

The Medusa URL variables are for local/demo setup readiness and Store API calls.
The frontend does not use them directly; it reads the generic RouteDeck
projection exposed by the app backend.

## Run

Backend:

```powershell
cd examples/medusa-agent/backend
python -m pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8098
```

Frontend:

```powershell
cd examples/medusa-agent/frontend
npm install
npm run dev
```

The frontend runs on `http://127.0.0.1:5198`.

## Test

Backend:

```powershell
cd examples/medusa-agent/backend
python -m pytest tests -q
```

Frontend:

```powershell
cd examples/medusa-agent/frontend
npm test
```

## Smoke Prompts

- `hi`
- `what can you help with?`
- `show me products`
- `I want to buy a t-shirt`
- `not sure`

Expected behavior: the assistant streams natural shopping help, asks focused
clarifying questions, and keeps product chat free of implementation details.

## Reset

Current reset remains process-local for conversations, opaque refs, and demo
cart state: restart the backend or clear the in-memory state. Slice 3 does not
include seeded catalog reset or fixture management.
