# RouteDeck Context

Last updated: 2026-06-09

## Current State

RouteDeck has a locked framework reference at `docs/route-deck-reference.md`.
That reference is the authority for framework language, ownership boundaries,
navgraph semantics, capabilities, surfaces, entity binding, planning context,
dispatch, diagnostics, events, and product boundaries.

The reference was expanded into a software-on-paper contract on 2026-06-06. It
now explicitly covers product/API plane ownership, path-shaped deeplink codecs
with query-owned surface/presentation state, product-agent SSE versus RouteDeck
state streams, diagnostics streams, planning-context normalization, action-chip
filtering, surface event resolution, dispatch semantics, schema field
responsibilities, Corpus lessons adopted into RouteDeck, and the Medusa
barebones reset.

`critical_prompt.md` now also carries compact guardrails for stream separation,
diagnostics, and `RouteDeckStore`: product-agent SSE, RouteDeck state SSE, and
diagnostics streams stay separate; diagnostics remain read-only and out of
public chat; `RouteDeckStore` mirrors runtime state and never becomes graph
truth.

The controlling strategic plan is
`docs/superpowers/plans/2026-06-08-routedeck-open-source-medusa-agent.md`. It
supersedes the older 2026-06-03 Medusa readiness plan wherever the older plan
conflicts with the Medusa chat-only reset. It sequences RouteDeck open-source
alpha completion and Medusa Agent rebuild as two locked lanes: RouteDeck gets
framework/package hardening, while Medusa first resets to Slice 1 app-owned chat
before RouteDeck behavior is reintroduced.

Implementation must execute from the micro-slice overlay at
`docs/superpowers/plans/2026-06-08-routedeck-medusa-micro-slices.md`. The
strategic plan explains the destination; the micro-slice overlay controls the
order of edits, test gates, stop points, and anti-drift checks.

The Medusa runnable example has now reached the corrected Slice 1 checkpoint:
chat-first, Foundation Agent-inspired shell, true app-owned SSE, static starter
prompt chips, read-only Route Map, read-only Inspector, URL-derived
`surface_id`, and no RouteDeck runtime/API, Store API, product write, checkout,
admin, or fake deterministic command-router behavior. See
`context_checkpoints/context_checkpoint_09-06-2026-2-38PM.md`.

The context architecture is now bootstrapped at the RouteDeck root so future
sessions can restart from local artifacts instead of chat history. This is a
thin bootstrap, not a full population of all downstream contracts.

## Active Work

- Keep `docs/route-deck-reference.md` stable unless the framework vision itself
  changes.
- Execute from `docs/superpowers/plans/2026-06-08-routedeck-medusa-micro-slices.md`
  when coding. Use
  `docs/superpowers/plans/2026-06-08-routedeck-open-source-medusa-agent.md` as
  the strategic map, not as a big-slice implementation checklist.
- Preserve the current Medusa Slice 1 as chat-first with read-only context
  scaffolding. Do not regress it to an empty chat page, and do not jump ahead to
  dynamic chips, Store API reads/writes, cart flows, or RouteDeck dispatch before
  the source-of-truth plumbing exists.
- Align downstream code and docs to the reference in a later session.
- Treat current core models, React store/types, and `examples/medusa-agent` as
  implementation targets that can be changed to match the reference.

## Deferred Downstream Alignment

Expected follow-up areas:

- `routedeck_core/models.py`: navgraph, capability, surface affordance, and
  entity/planning-context compatible schema alignment.
- `react/src/`: RouteDeckStore, types, hooks, and UI affordance handling aligned
  to projection/navgraph/capability semantics.
- `examples/medusa-agent/`: product-owned planning context, agent tools,
  surface affordances, navgraph visibility, and hidden route operation handling.
- Medusa dynamic chips: currently static starter prompts only; future chips must
  come from product planning context or projected capabilities, not frontend-only
  command lists.
- `docs/`: derived docs and plans reconciled with the locked reference.

## Validation Snapshot

Known recent validation for the reference guard:

```powershell
cd agent-lab-powered-projects/routedeck
python -m pytest tests/test_medusa_reference_slice0.py -q
```

Expected recent result: `12 passed`.

Known recent Medusa Slice 1 validation:

```powershell
cd agent-lab-powered-projects/routedeck/examples/medusa-agent/frontend
npm test

cd ..\backend
python -m pytest tests -q
```

Expected recent results: frontend `9 passed`, backend `10 passed`.

Run `python scripts/check_doc_coverage.py` before closeout when files are
changed.

## Boundaries To Preserve

- RouteDeck stays product-neutral.
- Product agents and product runtimes stay product-owned.
- Product APIs stay separate from generic `/api/routedeck/*` framework APIs.
- No deterministic phrase routing as a substitute for planning context and
  entity binding.
- No full context population around stale downstream code before alignment.
