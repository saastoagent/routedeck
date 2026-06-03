# System Flow Index - RouteDeck

Last updated: 2026-06-03

This is the compact source of truth for currently intended runtime and UX flows.
Use `context.md` for restart state and `architecture/components/` for subsystem
detail.

## Framework Spine

```text
Product graph truth
  -> RouteDeck navgraph
  -> capability contract
  -> RouteDeck projection
  -> surfaces, chat, automation, diagnostics
  -> affordance event or agent-selected capability request
  -> RouteDeck dispatch
  -> graph commit, rejection, review, or recovery
  -> semantic observation and next projection
```

Current anchors:

- Framework reference: `docs/route-deck-reference.md`
- Project setup: `README.md`
- Current context: `context.md`
- Code ownership map: `architecture/code-map.md`
- Component docs: `architecture/components/`
- Validation index: `test_index/README.md`

## Primary Interfaces

- Python schemas and helpers: `routedeck_core/`
- Optional LangGraph adapter: `routedeck_langgraph/`
- React client package: `react/src/`
- Product runtime shape: snapshot, projection, dispatch, inspect, stream
- Generic RouteDeck API plane in examples: `/api/routedeck/*`
- Product-owned agent API plane in examples: `/api/<product>/agent/stream`

## Main Runtime Flow

```text
product runtime or graph state
  -> RouteDeck projection and navgraph
  -> React surfaces or product-agent planning context
  -> dispatch input
  -> runtime validation
  -> accepted result, rejection, review, recovery, or next projection
```

Rules:

- Product graph truth is authoritative.
- Projection is a client-facing view.
- Surfaces emit semantic affordance events.
- Chat selects the same capabilities using planning context.
- Runtime validation resolves entity binding and commits or rejects.

## Diagnostic Flow

```text
runtime state
  -> RouteDeck introspection or diagnostics
  -> read-only explanation surface
```

Rules:

- Diagnostics are read-only unless explicitly designed otherwise.
- Diagnostics can expose framework details ordinary product UI should hide.
- Internal `route.*` operations stay hidden from ordinary product-agent planning
  context.

## Known Compatibility Debt

- The reference is ahead of downstream core, React, and Medusa example code.
- Full context population should follow downstream alignment.

## Validation Index

Fast reference guard:

```powershell
python -m pytest tests/test_medusa_reference_slice0.py -q
```

Architecture coverage advisory:

```powershell
python scripts/check_doc_coverage.py
```

Broader Python contract suite:

```powershell
python -m pytest tests -q
```

React suite:

```powershell
cd react
npm test
```
