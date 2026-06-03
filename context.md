# RouteDeck Context

Last updated: 2026-06-03

## Current State

RouteDeck has a locked framework reference at `docs/route-deck-reference.md`.
That reference is the authority for framework language, ownership boundaries,
navgraph semantics, capabilities, surfaces, entity binding, planning context,
dispatch, diagnostics, events, and product boundaries.

The context architecture is now bootstrapped at the RouteDeck root so future
sessions can restart from local artifacts instead of chat history. This is a
thin bootstrap, not a full population of all downstream contracts.

## Active Work

- Keep `docs/route-deck-reference.md` stable unless the framework vision itself
  changes.
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
- `docs/`: derived docs and plans reconciled with the locked reference.

## Validation Snapshot

Known recent validation for the reference guard:

```powershell
cd agent-lab-powered-projects/routedeck
python -m pytest tests/test_medusa_reference_slice0.py -q
```

Expected recent result: `12 passed`.

Run `python scripts/check_doc_coverage.py` before closeout when files are
changed.

## Boundaries To Preserve

- RouteDeck stays product-neutral.
- Product agents and product runtimes stay product-owned.
- Product APIs stay separate from generic `/api/routedeck/*` framework APIs.
- No deterministic phrase routing as a substitute for planning context and
  entity binding.
- No full context population around stale downstream code before alignment.
