# Context Checkpoint - 10-07-2026 08:51 AM IST

Project: RouteDeck
Branch: `saastoagent`
Status: Full-stack framework architecture locked; implementation is the next
goal.

## Locked Direction

RouteDeck is the default full-stack framework for robust agentic applications,
with LangGraph as the first-class execution substrate.

Two adoption modes share one kernel:

1. Full Flow: RouteDeck validates and compiles a declarative application into
   LangGraph execution plus events, SSE, projection, diagnostics, and React.
2. Core Integration: an existing agent/custom graph attaches through an
   executor adapter and receives the same state/interaction framework.

## Shared Event Contract

One typed event architecture carries explicit `assistant`, `runtime`, `tool`,
`surface`, and `diagnostic` channels with common event identity, correlation,
ordering, projection version, visibility, terminal, and replay semantics.

The application specification also exports the versioned frontend contract.
Dispatch is atomically claimed before executor invocation. A durable SQLite
reference backend must atomically persist public state, idempotent result, and
terminal event/outbox; interrupted external work is explicit and never silently
rerun.

## Current Implementation

Present:

- Python contracts/runtime foundation
- RouteDeckApp builder foundation
- LangGraph validation/common wiring
- React store/hooks/debugger
- Medusa reference integration
- committed Corpus direct-contract boundary checkpoint `189a6559`

Missing:

- complete Full Flow compiler
- production executor integration contract
- shared event/SSE kernel
- durable coordinated session/event/outbox backend
- backend-derived client contract and React loader/parity checks
- complete frontend contract generation/parity
- lightweight Corpus adoption
- standalone Full Flow and Core Integration examples

## Required Validation

The implementation plan requires compiler, integration, event/SSE, projection,
guard/review, React, example, clean-install, Corpus regression, and browser
acceptance tests.

## Next Session

Read `context.md`, ADR-001, ADR-002, and the full refactor plan. Execute the plan
test-first. Before starting services, ask the user to choose local, Mac mini LAN,
or Mac mini Tailscale.
