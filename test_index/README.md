# Test Index

This folder explains what RouteDeck validation protects, how to run it, and
which source subsystems it covers.

The current suites protect the transitional implementation. Active authority
flows from
[ADR-004](../decisions/ADR-004-routedeck-medusa-consumer-driven-runtime.md)
through the approved
[RouteDeck and Medusa buyer-agent design](../docs/superpowers/specs/2026-07-11-routedeck-medusa-agent-design.md)
to the
[consumer-driven implementation plan](../docs/superpowers/plans/2026-07-11-routedeck-medusa-agent-implementation.md).
The plan adds the target suites listed below; do not report them as passing
until those files exist and the commands have run. Runtime and release
verification are local Windows only.

## Suite Index

| Suite | Command | Protects | Source owner |
| --- | --- | --- | --- |
| Active design authority | `python -m pytest tests/test_active_design_authority.py -q` | ADR-004 -> approved design -> active plan, removal of the retired gate, and the local-only runtime decision. | Context architecture and handoff; tests and validation harness. |
| Reference guard | `python -m pytest tests/test_medusa_reference_slice0.py -q` | RouteDeck/Medusa reference boundaries, terminology authority, API-plane separation, and slice drift checks. | Packaging and public readiness; tests and validation harness. |
| Medusa reference example focused suite | `cd examples/medusa-agent/backend && python -m pytest tests/test_medusa_catalog.py tests/test_slice1_chat.py tests/test_slice2_projection.py tests/test_slice3_projection_surfaces.py -q`; `cd examples/medusa-agent/frontend && npm test -- --run` | Medusa app-owned chat SSE, separate RouteDeck state SSE, read-only Store API catalog/media projection, planning context, literal graph, dynamic projection chips, and product-media anti-drift guards. | Medusa reference example; tests and validation harness. |
| Python contract tests | `python -m pytest tests -q` | Core contracts, projection/runtime store contracts, LangGraph adapter, and reference guards. | Core contracts and runtime state; LangGraph adapter; tests and validation harness. |
| React tests | `cd react && npm test` | React store, hooks, debugger, TypeScript-facing runtime behavior. | React runtime, store, and debugger. |
| Architecture coverage advisory | `python scripts/check_doc_coverage.py` | Changed file ownership against `architecture/code-map.md`; advisory closeout warnings. | Architecture coverage docs; tests and validation harness. |

## Current Validation Priority

For ADR-004 authority and context-only changes, run:

```powershell
python -m pytest tests/test_active_design_authority.py -q
python scripts/check_doc_coverage.py
```

For downstream source alignment, run the focused suite for the changed subsystem
plus every framework/Medusa consumer test required by that implementation-plan
slice.

For Medusa visible-slice work, run the Medusa reference example focused suite
plus:

```powershell
python -m pytest tests/test_anti_drift_boundaries.py tests/test_medusa_reference_slice0.py -q
```

## Planned Consumer-Driven Validation Matrix

| Lane | Planned command | Required meaning |
| --- | --- | --- |
| Feature composition | `python -m pytest tests/app tests/navigation tests/projection -q` | Immutable features compile into one authoritative operation/navigation/surface/projection contract and versioned frontend export; invalid composition fails. |
| Interaction kernel | `python -m pytest tests/state tests/supervision -q` | Agent and UI actions use one executor path with server-authoritative state, atomic claims, version checks, guards, reviews, interruption, and typed outcomes. |
| Typed events and SSE | `python -m pytest tests/events tests/fastapi -q` | Typed payloads, channel/visibility isolation, sequence, persistence-before-fanout, replay, reconnect/reset, private-form separation, and terminal failure. |
| Durable SQLite backend | `python -m pytest tests/sqlite -q` | Atomic dispatch claims, state/result/terminal-event outbox, process reopen, replay durability, and honest interruption behavior. |
| Optional LangGraph middleware | `python -m pytest tests/langgraph -q` | Model/tool activity enters the shared supervised runner while RouteDeck core remains free of LangGraph and product behavior. |
| Boundary and conformance | `python -m pytest tests/conformance tests/test_boundary_rules.py -q` | Framework packages remain product-neutral, Medusa owns Store transport/commerce, and no fallback or alternate execution path crosses the boundary. |
| Headless and React packages | Run the `@routedeck/core`, `@routedeck/react`, and `@routedeck/testing` test/build/type-check scripts. | Generated-contract parity, event ordering/dedupe/replay, stale projection rejection, server authority, surfaces, private forms, review, navigation, and inspector behavior. |
| Standalone Medusa buyer agent | Run `python -m pytest examples/medusa-agent/backend/tests -q`, the Medusa frontend tests/build, then the plan's real-Medusa integration and configured-real-model gates. | Real local Medusa is the commerce source of truth; agent/UI actions converge through RouteDeck; order confirmation requires reviewed placement plus independent order re-read. |
| Browser and release proof | Run the Medusa Playwright suite and `examples/medusa-agent/scripts/release-verify.ps1` only when the active task authorizes the local stack. | Full guest-buyer flow, reload/replay/deep links/recovery/network boundaries, exact dependency and coverage gates, protected reset, and sanitized proof bundle all pass locally. |

The exact task-by-task commands and file paths live in
`docs/superpowers/plans/2026-07-11-routedeck-medusa-agent-implementation.md`.
Implementation, services, databases, browser automation, and release
verification run only on the local Windows development machine. Do not probe or
fall back to the Mac mini. Start services only in a plan task that expressly
authorizes them, and report the exact command and smoke URL.

## Update Rule

When adding, renaming, or deleting tests, update this index and the matching row
in `architecture/code-map.md`. Component docs under `architecture/components/`
should explain behavior-level contracts, not copy test implementation.
