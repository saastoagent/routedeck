# RouteDeck Context

Last updated: 2026-06-12

## Current State

RouteDeck is being prepared as an open-source, product-neutral agentic UI
framework. Medusa Agent is the product-owned reference example that proves the
RouteDeck contract without moving commerce behavior into framework code.

The current Medusa visible slice is now chat-first with read-only Store
API-backed projection:

- `POST /api/medusa-agent/agent/stream` carries assistant text only.
- `GET /api/medusa-agent/route-stream` carries RouteDeck projection/state
  updates for the same `conversation_id`.
- `GET /api/medusa-agent/projection` returns product-owned RouteDeck projection
  state for path plus optional `surface_id` query state.
- Product catalog facts, prices, and product images come from read-only Medusa
  Store API reads through `backend/services/medusa_catalog.py`.
- If Medusa Store API config/read fails, the UI must show catalog unavailable;
  it must not fabricate products or local product media.
- Product cards render projected `image_url` with
  `data-image-source="medusa_store_api"`.
- Local brand art lives under `/medusa-brand/*`; `/medusa-products/*` is banned
  from runtime frontend source.
- The Route Map is a literal `@xyflow/react` graph and is read-only orientation.
  Graph selection may focus the local inspector only; it must not dispatch,
  navigate, mutate graph truth, or change the browser URL.
- Prompt chips are chat prompts derived from projection presentation state.
  They are not `legal_operations`, route operations, or product write commands.
- Temporary debug context is still present through
  `GET /api/medusa-agent/debug/context-thread`; it exposes system/planning/user
  context for commit-readiness proof and should be removed before the public
  example is final.

Fresh browser evidence from 2026-06-11/12 showed `/browse?surface_id=browse.product_list`
rendering 4 Store API products: Medusa T-Shirt, Medusa Sweatshirt, Medusa
Sweatpants, and Medusa Shorts. Product media used Medusa public S3 URLs, no
`/medusa-products/*` DOM references existed, the graph retained 4 nodes and 3
edges, and the composer stayed visible.

The 2026-06-10 gap audit remains active as a regression guard: assistant prose
alone is not a state update, and public chat must not invent product facts. A
normal chat request that shows products must either drive the same product-owned
projection/runtime boundary as the visible surface or state that the fact/action
is unavailable in the current slice. Every visible product slice still needs
browser-proven chat-to-projection convergence before it can be called usable.

## Active Authorities

Read these first next session:

1. `critical_prompt.md`
2. `context.md`
3. `context_checkpoints/context_checkpoint_12-06-2026-medusa-store-api-projection.md`
4. `docs/route-deck-reference.md`
5. `docs/medusa-agent-reference-app.md`
6. `architecture/code-map.md`
7. `test_index/README.md`
8. `docs/superpowers/plans/2026-06-08-routedeck-medusa-micro-slices.md`
9. `examples/medusa-agent/frontend/design-qa.md`

The locked framework authority remains `docs/route-deck-reference.md`. The
Medusa reference-app authority is `docs/medusa-agent-reference-app.md`, updated
to require read-only Store API catalog/media reads and exclude Store API writes,
cart writes, checkout, payment, shipping, admin, private Medusa IDs, `rd_node`
canonical links, and RouteDeck-prefixed public routes.

## Active Boundaries

- RouteDeck core and React package stay product-neutral.
- Medusa product behavior stays in `examples/medusa-agent`.
- Product APIs stay under `/api/medusa-agent/*`; do not add public
  `/api/routedeck/*` product behavior routes.
- Chat SSE and RouteDeck state SSE stay separate.
- Product facts in public chat must come from projection/planning context or a
  product tool result. If unavailable, the assistant must say it cannot verify
  the fact yet.
- No deterministic phrase router, command table, fake catalog, hardcoded product
  answers, local product images, cart mutation, checkout, payment, shipping,
  admin, or write-capable Store API behavior.
- Do not call a visible slice ready until browser behavior, source, docs, and
  anti-drift tests have been compared against the reference and reviewed by a
  subagent.

## Changed Contract Since Previous Context

The old context said the Medusa checkpoint had no Store API and only static
starter prompts. That is stale.

Current contract:

- Store API reads are required for product catalog/media projection.
- Store API writes remain excluded.
- Route-stream is implemented and required for RouteDeck projection updates.
- The read-only `open_medusa_surface` tool exists for browse projection.
- Anti-drift tests now allow Store API wording but block `/medusa-products/*`
  runtime source and stale product-specific fallbacks.

## Context Architecture Closeout

This context rewrite is paired with:

- `logs/20260612_medusa_store_api_projection_closeout.md`
- `context_checkpoints/context_checkpoint_12-06-2026-medusa-store-api-projection.md`
- `context_history/20260612_context_before_medusa_store_api_projection_closeout.md`

`architecture/code-map.md` was updated for the Medusa reference example row.
`test_index/README.md` was updated with the Medusa focused validation suite.
No ADR was added because this was a reference-app contract correction and
slice closeout, not a new framework-wide decision beyond the updated reference
docs and guards.

## Validation Snapshot

Fresh validation from the Store API projection slice:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck\examples\medusa-agent\backend"
python -m pytest tests/test_medusa_catalog.py tests/test_slice1_chat.py tests/test_slice2_projection.py tests/test_slice3_projection_surfaces.py -q
```

Result: `27 passed`.

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck\examples\medusa-agent\frontend"
npm test -- --run
```

Result: `17 passed`.

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck"
python -m pytest tests/test_anti_drift_boundaries.py tests/test_medusa_reference_slice0.py -q
```

Result: `24 passed`.

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck\examples\medusa-agent\frontend"
npx vite build
```

Result: passed, with the known Node `22.9.0` warning because Vite prefers
`20.19+` or `22.12+`.

Run `python scripts/check_doc_coverage.py` before final closeout whenever docs
or source files move.

## Next Session

Start by inspecting the dirty RouteDeck diff and the checkpoint above. The next
practical step is to either commit/checkpoint this Store API-backed browse slice
or plan the next visible Medusa slice from the micro-slice overlay. Do not start
cart/write behavior next; keep the next slice read-only unless the reference
and plan are explicitly updated first.
