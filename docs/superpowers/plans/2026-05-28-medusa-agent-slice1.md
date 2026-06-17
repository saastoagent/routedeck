# Medusa Agent Slice 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first runnable `examples/medusa-agent` app as a normal commerce chat experience with a real streaming agent shell. Slice 1 uses a stripped-down copy of the `agent-lab-powered-projects/foundation-agent` architecture, but it does not introduce RouteDeck runtime APIs or real Medusa API integration.

**Architecture:** Slice 1 is an app-owned FastAPI backend plus a small React chat UI. The backend owns the Medusa commerce-chat agent, exposes `POST /api/medusa-agent/agent/stream`, streams true Server-Sent Events with `text/event-stream`, and runs a minimal LangGraph agent using OpenAI through LangChain. The default model is `gpt-5-mini`. Tests must not require a live OpenAI key; mocked execution is required for local validation. No fallback assistant behavior is allowed.

**Current RouteDeck Correction (post-M3.7):** This document is the historical
Slice 1 baseline. The active execution contract is now governed by
`docs/superpowers/plans/2026-06-08-routedeck-medusa-micro-slices.md`.
Active state-stream contract after M3.7: `GET /api/medusa-agent/route-stream`
is the product-owned RouteDeck state SSE for Medusa.
`POST /api/medusa-agent/agent/stream` must not emit `projection_update`.
Navgraph renderer: a visible navgraph is a literal node/edge graph.
Use a graph visualization library or dedicated graph renderer;
hand-positioned buttons with decorative lines are not sufficient once a slice
claims navgraph UI.

**Foundation-Agent Basis:** Reuse the proven shape, not the full app:

- Keep the true SSE event helper pattern from `agent-lab-powered-projects/foundation-agent/backend/core/protocol.py`.
- Keep the `StreamingResponse(..., media_type="text/event-stream")` route pattern from `agent-lab-powered-projects/foundation-agent/backend/routes/chat.py`.
- Keep the async stream orchestration idea from `agent-lab-powered-projects/foundation-agent/backend/services/chat_service.py`, reduced to one commerce agent and no persistence.
- Keep the minimal LangGraph/`ChatOpenAI(streaming=True)` builder shape from `agent-lab-powered-projects/foundation-agent/backend/services/graph_builder.py`, but remove all tools for Slice 1.
- Keep the frontend SSE parsing approach from `agent-lab-powered-projects/foundation-agent/frontend/src/hooks/useSSEChat.ts`, reduced to message streaming only.
- Drop auth, SQLAlchemy/database, admin pages, RAG, memory, document upload, tool router, citations, tool cards, source cards, RouteDeck imports, and Medusa Store/Admin API calls.

**Tech Stack:** Python 3.11, FastAPI, pytest, httpx, LangGraph, langchain-openai, React, Vite, TypeScript, Vitest, Testing Library.

**Latest Stable Dependency Pins Checked On 2026-05-28:**

Backend `requirements.txt` must use exact pins:

```text
fastapi==0.136.3
httpx==0.28.1
langchain-openai==1.2.2
langgraph==1.2.2
pytest==9.0.3
uvicorn==0.48.0
```

Frontend `package.json` must use exact pins:

```json
{
  "dependencies": {
    "@vitejs/plugin-react": "6.0.2",
    "react": "19.2.6",
    "react-dom": "19.2.6",
    "typescript": "6.0.3",
    "vite": "8.0.14"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "6.9.1",
    "@testing-library/react": "16.3.2",
    "jsdom": "29.1.1",
    "vitest": "4.1.7"
  }
}
```

These are example-local pins only. Do not change RouteDeck root package dependencies in Slice 1.

---

## Scope

Build only Slice 1:

- Natural commerce chat for the smoke prompts `hi`, `what can you help with?`, `show me products`, `I want to buy a t-shirt`, and `not sure`.
- One required backend endpoint: `POST /api/medusa-agent/agent/stream`.
- Optional backend endpoint: `GET /api/medusa-agent/health`.
- True SSE response format, not NDJSON.
- Minimal LangGraph agent path with OpenAI model default `gpt-5-mini`.
- LangGraph `stream_events(..., version="v2")` or `astream_events(..., version="v2")` is the graph-to-SSE source for compatibility with the installed LangGraph runtime.
- Process-local LangGraph checkpointing with `InMemorySaver`, using request `conversation_id` as `configurable.thread_id`.
- Explicit SSE error when `OPENAI_API_KEY` is not configured.
- No deterministic fallback assistant responses.
- Local `examples/medusa-agent/backend/.env` may be created from SaaStoAgent's
  `STA_OPENAI_API_KEY` by writing it as `OPENAI_API_KEY`; the file must remain
  gitignored.
- In-memory/process-local conversation state only.
- No RouteDeck runtime, manifest, projection, dispatch, inspect, or RouteDeck stream API is introduced in Slice 1.
- No `/api/routedeck/*`, Medusa API calls, cart, checkout, payment, shipping, admin mutation, Docker, seeded product catalog, or RouteDeck debugger UI.

## File Structure

- Create `examples/medusa-agent/README.md`: Slice 1 run commands, smoke prompts, env vars, and non-goals.
- Create `examples/medusa-agent/backend/main.py`: FastAPI app, CORS for local dev if needed, and route registration.
- Create `examples/medusa-agent/backend/app.py`: compatibility export for tests, importing `app` from `main.py`.
- Create `examples/medusa-agent/backend/core/config.py`: env-driven settings, including `OPENAI_API_KEY` and `MEDUSA_AGENT_MODEL`.
- Create `examples/medusa-agent/backend/core/protocol.py`: stripped SSE helpers.
- Create `examples/medusa-agent/backend/routes/chat.py`: `POST /api/medusa-agent/agent/stream` route.
- Create `examples/medusa-agent/backend/services/graph_builder.py`: minimal LangGraph commerce agent builder.
- Create `examples/medusa-agent/backend/services/chat_service.py`: stream orchestration, OpenAI execution, keepalive/error events.
- Create `examples/medusa-agent/backend/tests/test_slice1_chat.py`: backend contract tests.
- Create `examples/medusa-agent/backend/requirements.txt`: exact latest-stable backend pins listed above.
- Create `examples/medusa-agent/frontend/package.json`: Vite/Vitest scripts and dependencies.
- Create `examples/medusa-agent/frontend/index.html`: Vite mount point.
- Create `examples/medusa-agent/frontend/src/App.tsx`: first-screen chat app.
- Create `examples/medusa-agent/frontend/src/hooks/useSSEChat.ts`: stripped SSE hook targeting `/api/medusa-agent/agent/stream`.
- Create `examples/medusa-agent/frontend/src/main.tsx`: React bootstrap.
- Create `examples/medusa-agent/frontend/src/styles.css`: restrained app styling.
- Create `examples/medusa-agent/frontend/src/App.test.tsx`: frontend behavior tests.

## Public HTTP Contract

### `POST /api/medusa-agent/agent/stream`

Request:

```json
{
  "message": "I want to buy a t-shirt",
  "conversation_id": "optional-client-id"
}
```

`conversation_id` maps directly to LangGraph `config={"configurable": {"thread_id": conversation_id}}` when the graph path is used. If omitted, the backend generates a process-local id and returns it in `stream_start`.

Response headers:

```text
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no
```

Required event sequence:

```text
event: stream_start
data: {"conversation_id":"...","model":"gpt-5-mini"}

event: agent_start
data: {"agent_name":"medusa-commerce-agent"}

event: message_delta
data: {"content":"Hi. I can help you shop for demo products..."}

event: agent_end
data: {}

event: stream_end
data: {}
```

Allowed support events:

- `keepalive` comment frames as `: ping`
- `error` with `{ "message": "...", "code": "..." }`

Not allowed in Slice 1 stream data:

- RouteDeck operation ids, graph nodes, manifest ids, projection data, dispatch traces, or `/api/routedeck/*`.
- Medusa private ids, payment ids, shipping ids, admin credentials, or real cart/order ids.
- Tool lifecycle events, because Slice 1 has no tools.

## Agent And LLM Contract

Use a minimal LangGraph state graph with one `agent` node.

- The graph input is the conversation messages.
- Slice 1 graph state is raw `MessagesState` only.
- Do not store prompt strings, SSE frames, frontend state, or formatted UI text in graph state.
- The system prompt must describe a normal commerce shopping assistant for a Medusa demo.
- Compose the system prompt inside the node at execution time.
- The default model is `gpt-5-mini`.
- `MEDUSA_AGENT_MODEL` may override the model for local experimentation.
- `OPENAI_API_KEY` enables the live OpenAI/LangChain path.
- Without `OPENAI_API_KEY`, the service must emit an `error` event with code `openai_api_key_missing` and must not emit `message_delta`.
- Backend tests must exercise missing-key errors or a mocked LLM path, not the network.
- Live/mocked graph tests must prove assistant output is emitted as multiple `message_delta` SSE frames from the graph stream path, not as one post-hoc full-text response.
- The graph must not bind tools in Slice 1.
- The graph must not import RouteDeck packages or Medusa SDK/API clients.
- Future tool/checkout/admin confirmation flows must use LangGraph interrupts with a checkpointer and stable `thread_id`; Slice 1 must not introduce an ad hoc chat-command confirmation protocol.

Minimal graph shape:

```python
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, MessagesState, StateGraph
from langgraph.checkpoint.memory import InMemorySaver


def build_agent_graph(settings):
    llm = ChatOpenAI(
        model=settings.medusa_agent_model,
        api_key=settings.openai_api_key,
        streaming=True,
        temperature=0.3,
    )

    def agent_node(state: MessagesState):
        messages = [SystemMessage(content=COMMERCE_SYSTEM_PROMPT), *state["messages"]]
        return {"messages": [llm.invoke(messages)]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent_node)
    graph.set_entry_point("agent")
    graph.add_edge("agent", END)
    return graph.compile(checkpointer=InMemorySaver())
```

`chat_service.py` must call the compiled graph with:

```python
config = {"configurable": {"thread_id": conversation_id}}
stream = graph.stream_events({"messages": messages}, config=config, version="v2")
```

In async code, use `await graph.astream_events(..., version="v2")` if required by the installed API. Convert only message text/token projection output to product SSE `message_delta` frames. Do not call the graph once with `invoke()` and then split the completed response afterward.

## Task 1: Backend Contract Tests

**Files:**

- Create: `examples/medusa-agent/backend/tests/test_slice1_chat.py`
- Later create: backend files listed above.

- [ ] Write failing tests for:
  - `POST /api/medusa-agent/agent/stream` returns `text/event-stream`.
  - The stream includes `stream_start`, `agent_start`, `message_delta`, `agent_end`, and `stream_end`.
  - `stream_start` reports model `gpt-5-mini` by default.
  - `conversation_id` maps to LangGraph `thread_id` when the graph path is used.
  - Missing `OPENAI_API_KEY` emits an error event and no simulated assistant text.
  - Mocked graph streaming emits more than one `message_delta` frame.
  - The smoke prompts produce natural shopping-assistant responses.
  - `/api/routedeck/manifest` returns 404.
  - Stream text does not mention RouteDeck operations, graph nodes, dispatch, cart, checkout, payment, shipping, admin mutation, or Medusa private ids.

- [ ] Run from `examples/medusa-agent/backend` and verify RED:

```powershell
python -m pytest tests -q
```

Expected: fail because backend files do not exist yet.

## Task 2: Backend Implementation

**Files:**

- Create: `examples/medusa-agent/backend/main.py`
- Create: `examples/medusa-agent/backend/app.py`
- Create: `examples/medusa-agent/backend/core/config.py`
- Create: `examples/medusa-agent/backend/core/protocol.py`
- Create: `examples/medusa-agent/backend/routes/chat.py`
- Create: `examples/medusa-agent/backend/services/graph_builder.py`
- Create: `examples/medusa-agent/backend/services/chat_service.py`
- Create: `examples/medusa-agent/backend/requirements.txt`

- [ ] Add settings:
  - `OPENAI_API_KEY`
  - `MEDUSA_AGENT_MODEL`, default `gpt-5-mini`
  - local `.env` loading for `OPENAI_API_KEY` and `MEDUSA_AGENT_MODEL`

- [ ] Implement `core/protocol.py` with true SSE:

```python
def encode_sse(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"
```

- [ ] Implement helper events:
  - `stream_start(conversation_id, model)`
  - `agent_start("medusa-commerce-agent")`
  - `message_delta(content)`
  - `agent_end()`
  - `stream_end()`
  - `error(message, code)`
  - `keepalive()`

- [ ] Implement `services/graph_builder.py` as the minimal no-tool LangGraph agent using `ChatOpenAI(streaming=True)`, model `gpt-5-mini` by default, and `InMemorySaver`.

- [ ] Implement `services/chat_service.py`:
  - validate non-empty message
  - generate or accept `conversation_id`
  - pass `conversation_id` to LangGraph as `configurable.thread_id`
  - emit `stream_start`
  - emit `agent_start`
  - if `OPENAI_API_KEY` is configured, consume `graph.stream_events(..., version="v2")` or `graph.astream_events(..., version="v2")` and convert message token/text projection output to `message_delta`
  - if `OPENAI_API_KEY` is missing, emit an `error` event and do not produce assistant text
  - emit `agent_end`
  - emit `stream_end`
  - emit `error` if validation or execution fails
  - enforce a bounded model-call timeout; Slice 1 may convert timeout/rate-limit failures to product-language SSE `error` without retry

- [ ] Implement `routes/chat.py` with:

```python
StreamingResponse(
    generate(),
    media_type="text/event-stream",
    headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    },
)
```

- [ ] Verify GREEN:

```powershell
python -m pytest tests -q
```

## Task 3: Frontend SSE Chat

**Files:**

- Create: `examples/medusa-agent/frontend/package.json`
- Create: `examples/medusa-agent/frontend/index.html`
- Create: `examples/medusa-agent/frontend/src/App.tsx`
- Create: `examples/medusa-agent/frontend/src/hooks/useSSEChat.ts`
- Create: `examples/medusa-agent/frontend/src/main.tsx`
- Create: `examples/medusa-agent/frontend/src/styles.css`
- Create: `examples/medusa-agent/frontend/src/App.test.tsx`

- [ ] Write failing tests for:
  - first screen is chat, not a landing page
  - sending `hi` calls `/api/medusa-agent/agent/stream`
  - true SSE chunks are parsed incrementally from `event:` / `data:` frames
  - `message_delta` appends assistant text
  - `stream_end` clears streaming state
  - no RouteDeck/debugger UI is rendered

- [ ] Implement a stripped `useSSEChat.ts`:
  - use `XMLHttpRequest` or fetch streaming reader
  - parse frames shaped as `event: <type>\ndata: <json>\n\n`
  - handle `message_delta`, `stream_start`, `agent_start`, `agent_end`, `stream_end`, and `error`
  - target `/api/medusa-agent/agent/stream`

- [ ] Implement `App.tsx` as the first screen:
  - conversation list
  - message composer
  - streaming assistant bubble
  - no card-heavy landing page
  - no RouteDeck operation/debugger language

- [ ] Verify GREEN:

```powershell
npm install
npm test
```

## Task 4: Documentation And Scope Guards

**Files:**

- Create: `examples/medusa-agent/README.md`
- Modify: `tests/test_medusa_reference_slice0.py`

- [ ] Add or extend a guard test that scans `examples/medusa-agent` after Slice 1 exists and fails on:
  - `/api/routedeck/`
  - `routedeck_core`
  - `routedeck_langgraph`
  - `@routedeck/react`
  - Medusa Store/Admin API client imports
  - checkout/cart/payment/shipping/admin mutation implementation

- [ ] Add README sections:
  - Slice 1 purpose
  - foundation-agent subset used
  - pinned dependency versions checked on 2026-05-28
  - env vars, including `MEDUSA_AGENT_MODEL=gpt-5-mini`
  - backend and frontend run commands
  - smoke prompts
  - explicit non-goals

- [ ] Run full Slice 1 verification:

```powershell
cd examples/medusa-agent/backend
python -m pytest tests -q
cd ..\frontend
npm test
cd ..\..\..
python -m pytest tests -q
```

## Manual Acceptance

From the RouteDeck root, the backend acceptance command is:

```powershell
python -m pytest examples/medusa-agent/backend/tests -q
```

From `examples/medusa-agent/frontend`, the frontend acceptance command is:

```powershell
npm test
```

Manual smoke:

- Launch backend on port `8098`.
- Launch frontend on port `5198`.
- In the browser, verify the first screen is the chat app.
- Send `hi`, `what can you help with?`, `show me products`, `I want to buy a t-shirt`, and `not sure`.
- Confirm the response streams visibly.
- Confirm the assistant answers naturally, asks clarifying questions, and never mentions RouteDeck, operation ids, graph nodes, dispatch, cart, checkout, payment, shipping, admin, or Medusa private ids.

## Assumptions

- Slice 1 may install example-local backend and frontend dependencies.
- Slice 1 may use the live OpenAI path only when `OPENAI_API_KEY` is configured.
- Slice 1 tests must pass without network access by using mocked graph execution and missing-key error assertions.
- Slice 1 is not responsible for connecting to a real Medusa instance. That starts in Slice 2.
- Slice 1 reset is process-local: restart the backend or clear in-memory conversation state.
