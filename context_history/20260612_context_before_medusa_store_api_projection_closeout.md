# RouteDeck Context Archive

Archived on: 2026-06-12

Source: `context.md` before the Medusa Store API projection closeout rewrite.

## Current State

2026-06-09 recalibration: the next visible slice is Medusa Agent powered by
RouteDeck, not a new product-neutral RouteDeck dashboard/demo. A prior
product-neutral minimal FastAPI/React example was created in error and must be
deleted before the Medusa slice is reported ready. Future RouteDeck/Medusa work
must use subagents for reference extraction and drift review, then compare the
browser behavior and code against `critical_prompt.md`,
`docs/route-deck-reference.md`, the Medusa micro-slice plan, and
`tests/test_anti_drift_boundaries.py` before claiming readiness.

2026-06-10 gap audit: the visible Medusa shell exposed projection/surface
scaffolding, but chat could still answer product requests without moving the
projection or grounding product facts. Future slices must not call that state
usable. Once a product projection or product surface is visible, chat requests
such as "show products" or "show the t-shirt" must either drive the same
product-owned RouteDeck runtime boundary and next projection as the matching
surface affordance, or explicitly say that the action/fact is not available in
the current slice.

The visible product example must stay inside `examples/medusa-agent/` unless
the user explicitly asks for a separate product-neutral example. Medusa Agent
is chat-first: Foundation Agent-style shell, real product-owned SSE assistant
stream, assistant starter turn with action chips, RouteDeck underneath as
projection/state/navgraph/capability/dispatch plumbing, and no separate
RouteDeck dashboard replacing the product agent experience.

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

The Medusa runnable example has now reached a transitional checkpoint: Slice 1
chat-first shell plus read-only projection/orientation scaffolding. This is not
pure Slice 1, because pure Slice 1 has no RouteDeck projection, Route Map,
Inspector, or `surface_id`. It is also not a usable product-surface slice,
because chat-to-projection convergence and product-fact grounding are not yet
proven. The current checkpoint includes a Foundation Agent-inspired shell, true
app-owned SSE, static starter prompt chips, read-only Route Map, read-only
Inspector, URL-derived `surface_id`, and no Store API, product write, checkout,
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
- Preserve the current Medusa transitional checkpoint as chat-first with
  read-only projection/orientation scaffolding. Do not regress it to an empty
  chat page, and do not jump ahead to dynamic chips, Store API reads/writes, cart
  flows, or RouteDeck dispatch before the source-of-truth plumbing exists.
- Do not call a projection/surface slice usable until chat-to-projection
  convergence is proven in the browser: a normal chat request must update the
  visible projected surface through an accepted runtime read operation, not just
  return assistant prose.
- Public chat must answer product names, prices, colors, sizes, availability,
  and cart state only from projection/planning context or a product tool result.
  If that context is missing, the assistant must ask for setup or say it cannot
  verify the fact yet.
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
  surface affordances, navgraph visibility, hidden route operation handling, and
  chat-to-projection convergence for read-only product browse/detail requests.
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
