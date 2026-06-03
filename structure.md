# Structure - RouteDeck

Last updated: 2026-06-03

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
  routedeck_langgraph/
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
| `routedeck_core/` | Core contracts and runtime state | Product-neutral Python models, projections, operations, events, validation helpers. |
| `routedeck_langgraph/` | LangGraph adapter | Optional bridge for LangGraph validation and graph wiring. |
| `react/src/` | React runtime, store, and debugger | Client store, hooks, surfaces, debugger, and TypeScript contracts. |
| `examples/` | Minimal examples | Product-neutral examples and the Medusa reference example. |
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
