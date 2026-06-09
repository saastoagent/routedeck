# Context Checkpoint - 09-06-2026 2:38PM

## Current State

The Medusa runnable example is now a corrected Slice 1 chat-first proof.

It is not the earlier empty chat-only reset. It now uses the Foundation Agent
chat shell pattern and preserves the RouteDeck visual vision through read-only
context scaffolding.

Current visible behavior:

- Medusa Agent opens on a chat-first shell.
- The composer is visible in the desktop viewport without body scrolling.
- Prompt chips are visible and send ordinary chat SSE messages.
- Route Map is visible as read-only orientation.
- Inspector is visible as read-only context.
- `surface_id` is displayed from URL/query-derived presentation state.
- Chat is the only active behavior.

Current runtime behavior:

- `POST /api/medusa-agent/agent/stream` is the only Slice 1 product behavior
  endpoint besides health.
- Backend streams real SSE frames.
- Frontend consumes SSE through XHR `onprogress`.
- LangGraph conversation continuity maps `conversation_id` to
  `configurable.thread_id`.
- Missing `OPENAI_API_KEY` emits an honest SSE error.
- When configured, the live model returns concise commerce-assistant text.

## Completed Work

- Removed later-slice RouteDeck runtime/API/store/Medusa Store drift from the
  runnable example.
- Replaced the frontend with a Foundation Agent-inspired Medusa chat shell.
- Added read-only Route Map and Inspector scaffolding without dispatch.
- Added prompt chips as static starter prompts only.
- Fixed desktop page height so the composer stays visible.
- Added/updated tests for SSE, missing-key behavior, route absence, UI shell,
  drift boundaries, and layout height.
- Updated `examples/medusa-agent/README.md`.
- Updated root Medusa guard in `tests/test_medusa_reference_slice0.py`.

## Not Done Yet

- Dynamic action chips are not implemented.
- Prompt chips are not generated from RouteDeck capabilities or planning
  context.
- RouteDeck projection/runtime/store is not reintroduced into Medusa.
- Medusa Store API reads are not implemented.
- Product cards, variant selection, cart writes, checkout, payment, shipping,
  admin, and order flows are not implemented.
- RouteDeck diagnostics/state stream is not implemented in the example.

## Drift Boundary

Allowed now:

- chat-first Medusa UI
- static starter prompt chips
- read-only Route Map
- read-only Inspector
- URL/path-derived read-only `surface_id`
- true app-owned chat SSE

Forbidden now:

- fake deterministic command router
- hardcoded product write behavior
- dynamic chips pretending to be projected capabilities
- RouteDeck runtime/API routes in Medusa Slice 1
- `/api/routedeck/*` product behavior
- `/api/medusa-agent/action`, projection, inspect, route-stream, or state
  runtime endpoints
- Store API calls
- private product/variant/cart/line ids in public UI or chat
- checkout/payment/shipping/admin/order behavior

## Validation Snapshot

Frontend:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck\examples\medusa-agent\frontend"
npm test
```

Result: `9 passed`.

Backend:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck\examples\medusa-agent\backend"
python -m pytest tests -q
```

Result: `10 passed`.

Root guard:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck"
python -m pytest tests/test_medusa_reference_slice0.py -q
```

Result: `12 passed`.

Browser checks:

- first screen had Medusa Agent, Route Map, Inspector, prompt chips, composer,
  and `surface_id`
- prompt chip sent SSE chat turn
- streaming state appeared
- live model response completed and returned to Ready
- no console warnings/errors
- mobile viewport retained core shell
- desktop height check returned `documentScrolls: false` and
  `composerVisible: true`

## First Files To Read Next Session

1. `critical_prompt.md`
2. `context.md`
3. `context_checkpoints/context_checkpoint_09-06-2026-2-38PM.md`
4. `docs/route-deck-reference.md`
5. `docs/superpowers/plans/2026-06-08-routedeck-medusa-micro-slices.md`
6. `examples/medusa-agent/README.md`
7. `examples/medusa-agent/frontend/src/App.tsx`
8. `examples/medusa-agent/frontend/src/hooks/useSSEChat.ts`
9. `examples/medusa-agent/backend/services/chat_service.py`
10. `tests/test_medusa_reference_slice0.py`

## Recommended Next Step

Do not add dynamic chips directly from the frontend. The next safe sequence is:

1. checkpoint or commit current Medusa Slice 1 separately
2. complete the RouteDeck framework/open-source gate
3. add Medusa projection-only/read-only runtime grounding
4. generate chips from product planning context/projected capabilities
5. only then add surface event dispatch

The immediate next implementation slice should prove where dynamic chips come
from, not merely make the existing static chips look dynamic.
