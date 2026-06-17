# Context Checkpoint - 12-06-2026 Medusa Store API Projection

## Current State

The Medusa Agent reference example is now a chat-first, read-only
Store API-backed RouteDeck proof.

Current visible behavior:

- Medusa Agent opens on a chat-first shell.
- The central stream starts with an assistant turn.
- Prompt chips are visible and come from projection presentation state.
- Clicking `Show me products` sends an ordinary chat prompt and can move the
  browser to `/browse?surface_id=browse.product_list` through RouteDeck state
  SSE.
- Browse projection renders current Store API products as assistant transcript
  attachment content.
- Route Map is a literal `@xyflow/react` graph with Home -> Browse -> Detail ->
  Cart.
- Route Map selection is read-only inspector focus only.
- Inspector is secondary read-only context.
- Composer is visible in the desktop viewport.

Current runtime behavior:

- Chat text streams through `POST /api/medusa-agent/agent/stream`.
- RouteDeck projection updates stream through
  `GET /api/medusa-agent/route-stream`.
- `conversation_id` maps to LangGraph `configurable.thread_id`.
- `open_medusa_surface` is the only current read-only tool path for browse
  projection.
- `backend/services/medusa_catalog.py` reads `/store/regions` and
  `/store/products` using `MEDUSA_BACKEND_URL` and
  `MEDUSA_PUBLISHABLE_API_KEY`.
- Product facts and media are normalized into public projection props without
  private Medusa IDs.
- Missing Store API config/read failure renders catalog unavailable instead of
  fake products.
- Temporary debug context remains available through
  `/api/medusa-agent/debug/context-thread`.

## Completed Work

- Corrected the prior Store API contradiction in docs and README.
- Added Store API-backed catalog/media adapter and tests.
- Reworked projection to consume catalog snapshots instead of static product
  constants.
- Reworked frontend product cards to use projected Store API image URLs.
- Removed local product image assets from runtime.
- Moved local brand art to `/medusa-brand/medusa-mark.png`.
- Added route-stream event bus/hook for separate RouteDeck state SSE.
- Added dynamic projection-backed prompt chips.
- Added browser/design QA evidence.
- Updated anti-drift tests to allow Store API wording but block
  `/medusa-products/*`.
- Updated `architecture/code-map.md`, `test_index/README.md`, `context.md`, and
  log/checkpoint context architecture files.

## Drift Boundary

Allowed now:

- chat-first Medusa UI
- read-only Store API catalog/media reads
- projection-backed product cards
- separate chat SSE and RouteDeck state SSE
- read-only literal navgraph
- read-only inspector/debug context
- dynamic chat prompt chips from projection presentation state

Forbidden now:

- fake deterministic command router
- hardcoded product catalog or product facts in runtime
- local product media under `/medusa-products/*`
- Store API writes
- cart mutation, checkout, payment, shipping, admin, order behavior
- public `/api/routedeck/*` product behavior routes
- action/inspect/dispatch endpoints treated as ready
- graph clicks that navigate, dispatch, or mutate graph truth
- claiming readiness without browser evidence, source audit, anti-drift tests,
  and subagent review

## Validation Snapshot

Backend:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck\examples\medusa-agent\backend"
python -m pytest tests/test_medusa_catalog.py tests/test_slice1_chat.py tests/test_slice2_projection.py tests/test_slice3_projection_surfaces.py -q
```

Result: `27 passed`.

Frontend:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck\examples\medusa-agent\frontend"
npm test -- --run
```

Result: `17 passed`.

RouteDeck anti-drift/reference:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck"
python -m pytest tests/test_anti_drift_boundaries.py tests/test_medusa_reference_slice0.py -q
```

Result: `24 passed`.

Build:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck\examples\medusa-agent\frontend"
npx vite build
```

Result: passed with known Node `22.9.0` warning.

Browser checks:

- browse URL rendered 4 Store API products
- image sources were `medusa_store_api`
- product image URLs were Medusa public S3 URLs
- `/medusa-products/*` was absent from DOM
- `/medusa-brand/medusa-mark.png` rendered brand art
- route graph retained 4 nodes and 3 edges
- composer visible

Subagent review:

- Initial review: fail on docs/tests drift and product-media path loophole.
- Re-review: pass after fixes.

Doc coverage:

```powershell
python scripts/check_doc_coverage.py
```

Result: exit `0`, advisory only. The package-lock unmapped warning was fixed by
updating `architecture/code-map.md`; remaining warnings are documented in
`logs/20260612_medusa_store_api_projection_closeout.md`.

## First Files To Read Next Session

1. `critical_prompt.md`
2. `context.md`
3. `logs/20260612_medusa_store_api_projection_closeout.md`
4. `docs/medusa-agent-reference-app.md`
5. `architecture/code-map.md`
6. `test_index/README.md`
7. `examples/medusa-agent/frontend/design-qa.md`
8. `examples/medusa-agent/backend/services/medusa_catalog.py`
9. `examples/medusa-agent/backend/services/routedeck_projection.py`
10. `examples/medusa-agent/frontend/src/App.tsx`

## Recommended Next Step

Inspect and commit/checkpoint this Store API-backed browse slice separately from
unrelated workspace changes. If implementation continues before commit, keep the
next visible slice read-only and derive it from the micro-slice plan; do not add
cart/write behavior yet.
