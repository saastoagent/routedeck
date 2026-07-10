# Structure - RouteDeck

Last updated: 2026-07-10

This is a maintained project tree and source ownership snapshot, not a full
recursive listing.

## Root

```text
routedeck/
  critical_prompt.md
  context.md
  context_pipeline.md
  instructions.md
  work_prompt.md
  structure.md
  SYSTEM_FLOW_INDEX.md
  README.md
  pyproject.toml
  architecture/
  docs/
  examples/
  react/
  routedeck_core/
  routedeck_fastapi/       # planned by the active refactor
  routedeck_langgraph/
  routedeck_sqlite/        # planned durable single-host backend
  routedeck_testing/       # planned shared conformance harness
  scripts/
  skills/
  tests/
  test_index/
  logs/
  context_checkpoints/
  context_history/
  plans/
  decisions/
  knowledgebase/
  audits/
  errors/
```

## Source Ownership

| Path | Owner subsystem | Notes |
| --- | --- | --- |
| `routedeck_core/` | Core contracts and interaction kernel | Product-neutral application specification, server-authoritative sessions, projections, operations, review, typed events, and validation. |
| `routedeck_langgraph/` | LangGraph execution | First-class Full Flow compiler and existing/custom LangGraph executor adapter. |
| `routedeck_fastapi/` | FastAPI/SSE transport (planned) | Product-neutral session, dispatch, review, inspect, typed event channel, and replay routes. |
| `routedeck_sqlite/` | Durable reference backend (planned) | Transactional session, dispatch claim, idempotent result, event log, replay, and outbox for single-host deployments. |
| `routedeck_testing/` | Conformance harness (planned) | Shared assertions run against Full Flow, Core Integration, backend implementations, and Corpus. |
| `react/src/` | React runtime, store, and debugger | Client store, hooks, surfaces, debugger, and TypeScript contracts. |
| `examples/` | Adoption examples | Medusa reference plus planned self-contained Full Flow change-planner and Core Integration document-review projects. |
| `docs/` | Packaging and public readiness | Framework docs, reference docs, whitepaper, and reference-app specs. |
| `architecture/` | Architecture coverage docs | Code map and component docs. |
| `skills/` | Repo-local skills and scaffolding | Repeatable RouteDeck workflows. |
| `tests/`, `react/tests/` | Tests and validation harness | Python and React contract tests. |
| Root context files and lifecycle folders | Context architecture and handoff | Restart state, handoff prompts, logs, checkpoints, and lifecycle docs. |

## Generated / Ignored Paths

- `.pytest_cache/` - pytest cache.
- `__pycache__/` - Python bytecode cache.
- `react/node_modules/` - npm dependencies when installed.
- `react/dist/` - package build output when generated.

## Update Rule

Update this file when a major directory, subsystem boundary, or generated path
changes. Update `architecture/code-map.md` for source-to-test/doc ownership.
