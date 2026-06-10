# Medusa Agent

This example is the first usable Medusa reference-app slice. It proves a normal
app-owned commerce chat agent in the visual shell expected by the RouteDeck
vision, with a small read-only RouteDeck projection grounding layer.

## Scope

Implemented scope includes:

- FastAPI backend owned by this app.
- React chat UI copied from the useful Foundation Agent shell pattern: avatar
  rows, timestamped bubbles, prompt chips, textarea composer, and thinking state.
- Product-owned read-only projection endpoint at
  `GET /api/medusa-agent/projection`.
- Projection-backed Route Map and Inspector that reflect product paths plus
  optional `surface_id` query state while keeping chat as the only active
  behavior.
- True Server-Sent Events at `POST /api/medusa-agent/agent/stream`.
- Minimal no-tool LangGraph commerce agent with default model `gpt-5-mini`.
- Explicit error event when `OPENAI_API_KEY` is not configured.
- Process-local conversation continuity with `conversation_id` mapped to
  `configurable.thread_id`.
- Temporary debug context view backed by
  `GET /api/medusa-agent/debug/context-thread`; this is a short-lived
  commit-readiness aid that exposes the full prompt/context/message thread and
  should be removed before the public example is treated as final.

This usable slice intentionally excludes:

- Public `/api/routedeck/*` routes.
- Product action, inspect, route stream, dispatch, full diagnostics panels,
  product surface events, and writes.
- Clickable navgraph behavior, product surface dispatch, add-to-cart controls,
  checkout, or Store API behavior.
- Medusa Store API reads or writes.
- Product catalog, variant selection, cart, checkout, payment, shipping, admin,
  seeded data, Docker, reset automation, and order flows.
- Deterministic phrase routers, command menus, fake product catalogs, or fallback
  assistant text when the model cannot run.

## Foundation-Agent Subset

This app keeps only the small Foundation Agent shape needed for a polished chat
shell and streaming:

- SSE frame helpers.
- FastAPI `StreamingResponse` route.
- Async stream orchestration.
- LangGraph commerce assistant.
- XHR-based SSE parsing in React.
- Foundation-style chat layout, prompt chips, message timestamps, and composer.

Auth, database persistence, product APIs, tool calls, citations, memory, upload
flows, commerce writes, and framework diagnostics are intentionally omitted.

## Dependencies

Backend pins:

```text
fastapi==0.136.3
httpx==0.28.1
langchain-openai==1.2.2
langgraph==1.2.2
pytest==9.0.3
pytest-asyncio==1.4.0
uvicorn==0.48.0
```

Frontend pins:

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
```

For this checkout, the backend also reads `examples/medusa-agent/backend/.env`.
That file is gitignored.

`OPENAI_API_KEY` is required for agent responses. Without it, the backend emits
an SSE `error` event with code `openai_api_key_missing`. Slice 1 intentionally
does not include fallback assistant text.

## Run

Backend:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck\examples\medusa-agent\backend"
python -m pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8098
```

Frontend:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck\examples\medusa-agent\frontend"
npm install
npm run dev
```

The frontend runs on `http://127.0.0.1:5198` and proxies
`/api/medusa-agent/*` to the backend on `http://127.0.0.1:8098`.

## Read-Only Projection

The projection endpoint is product-owned:

```text
GET /api/medusa-agent/projection?path=/detail/t-shirt&surface_id=detail.product_detail
```

Canonical visible paths are product paths, not framework query routes:

- `/`
- `/browse`
- `/detail/t-shirt`
- `/cart`

`surface_id` is optional query state for restoring the active surface. The path
remains the canonical public location. The example must not expose `rd_node`,
private Medusa IDs, operation payloads, or hidden dispatch state in the URL.

## Test

Backend:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck\examples\medusa-agent\backend"
python -m pytest tests -q
```

Frontend:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck\examples\medusa-agent\frontend"
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

Reset is process-local: restart the backend to clear conversation memory. No
database, Medusa container, seeded catalog, payment provider, or admin
credential is required.
