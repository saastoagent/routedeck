# RouteDeck Context

Last updated: 2026-07-11
Status: ADR-004 activates the approved RouteDeck and Medusa buyer-agent design
and its consumer-driven implementation plan. Execution is local Windows only.

## Start Here

1. [Critical prompt](./critical_prompt.md)
2. [ADR-004: RouteDeck And Medusa Advance Through Consumer-Driven Runtime Slices](./decisions/ADR-004-routedeck-medusa-consumer-driven-runtime.md)
3. [Approved RouteDeck and Medusa buyer-agent design](./docs/superpowers/specs/2026-07-11-routedeck-medusa-agent-design.md)
4. [Active implementation plan](./docs/superpowers/plans/2026-07-11-routedeck-medusa-agent-implementation.md)
5. [Current context](./context.md)
6. [Decision index](./decisions/README.md)
7. [RouteDeck reference](./docs/route-deck-reference.md) for existing feature vocabulary and payloads,
   subject to ADR-004 and the approved design where older target language conflicts
8. [Architecture code map](./architecture/code-map.md)
9. [Test index](./test_index/README.md)
10. [SaaStoAgent/Corpus context](../saastoagent-v0.1/context.md) as historical feature evidence and an existing integration boundary

Do not resume the
[retired full-stack refactor plan](./docs/superpowers/plans/2026-07-10-routedeck-full-stack-framework-refactor.md).
It is retained as historical material only.

## Active Implementation Authority

The authority chain is ADR-004 -> approved design -> active implementation
plan. ADR-003 remains historical rationale for RouteDeck's product identity and
tool-supervision boundary, but no longer controls sequencing or defers the
approved runtime work.

## Locked Product Direction

RouteDeck is state management and interaction governance for agentic
applications.

Its job is to keep the agent grounded in the current application state:

- give the agent only the context it currently needs
- expose only currently legal tools/operations
- preserve real identifiers from visible product data
- reject fabricated, stale, hidden, or ineligible identifiers
- apply product-supplied guards and review requirements
- manage navgraph location, navigation history, active surfaces, selections,
  feedback, and relevant tool-result context
- keep backend interaction state, SSE updates, and frontend projection aligned

The navgraph is the application's interaction map, not the agent's execution
graph. It describes user-facing states, transitions, tools, surfaces, deep
links, and recovery behavior.

## Tool Supervision Boundary

Every application-semantic read or write tool call must cross RouteDeck before
execution.

```text
agent proposes tool call
  -> RouteDeck allows, blocks, requests input, or requires review
  -> host agent runtime invokes the product tool only when allowed
  -> host reports result/failure to RouteDeck
  -> RouteDeck updates interaction/session state, context, surfaces, and events
```

RouteDeck does not call the tool. It oversees the call and returns structured
feedback. The host application owns the agent runtime, product tools, domain
records, authentication system, prompts, model calls, and side effects.

## Real Identifier Rule

Opaque RouteDeck IDs are not part of the first release. Trusted product
providers expose real IDs in the current projection. RouteDeck accepts an ID
only when it is in the current allowlist for that tool/operation and session
state. Public product responses still redact internal IDs when they should not
be shown to the user.

## Medusa Is The First Consumer

The standalone Medusa guest-buyer agent now drives RouteDeck development
through consumer-driven vertical slices. Each slice introduces only the
framework capability immediately consumed by matching Medusa behavior. A
RouteDeck-only result never completes a slice; the corresponding Medusa backend
and browser behavior must also work at the plan's required gates.

The Medusa application owns Store API access, commerce models, providers,
guards, handlers, LangGraph prompt/model behavior, and product surfaces.
RouteDeck owns product-neutral feature composition, interaction/session state,
supervision, persistence, transport, and frontend synchronization. Product
handlers execute only through the injected host executor.

Corpus remains an existing integration and useful historical behavior
reference, but it no longer controls implementation sequencing. Preserve the
Medusa **2026-06-10 gap audit** and its **chat-to-projection convergence** rule
as acceptance evidence for the standalone buyer agent.

## Current Implementation Reality

Already present:

- product-neutral manifest, navgraph, projection, operation, context-lens,
  entity, surface, dispatch, event, and diagnostics contracts
- generic navigation, operation policy, projection, review, and surface helpers
- an optional `routedeck_langgraph` package
- React provider/store/hooks and product surface integration helpers
- a feature-rich Corpus runtime that demonstrates the intended behavior but
  still contains generic RouteDeck mechanics

Known gaps relative to ADR-004:

- the immutable feature-composition API and runtime bindings are not yet in the
  approved package structure
- the single supervised operation runner, durable session/event state, SQLite
  adapter, and generic FastAPI/SSE transport are not yet complete
- optional LangGraph middleware and the new headless/React packages still need
  the approved boundary and conformance proof
- the current Medusa reference code must be replaced slice-by-slice by the
  standalone buyer agent without moving commerce logic into RouteDeck
- older docs still contain historical Full Flow, two-mode, Corpus-first, and
  deferral language; ADR-004 and the approved design control when they conflict

## Approved Runtime Scope

ADR-004 authorizes feature-composed authoring, durable RouteDeck session and
event state, generic FastAPI/SSE and SQLAlchemy SQLite/PostgreSQL adapters, optional LangGraph
middleware, headless/React packages, and the standalone Medusa buyer-agent
portability proof.

RouteDeck still does not own product tool execution or Medusa business logic.
The product supplies an injected executor, real Store API data, and explicit
handlers/providers/guards. Missing data, credentials, dependencies, or
invariants fail visibly; product paths do not substitute fixtures, canned
responses, heuristic routing, or silent fallbacks.

## Migration And Validation Rule

1. Write the focused failing framework or consumer test for the slice.
2. Add only the RouteDeck capability immediately consumed by Medusa.
3. Route both agent and UI operations through the same supervised runner.
4. Prove the matching Medusa backend and browser behavior against real local
   sources of truth at the plan's required integration gates.
5. Remove legacy or duplicate paths only after replacement and boundary proof.

Implementation, databases, services, test stacks, browser automation, and
release verification run on the local Windows development machine. Do not
probe, select, or fall back to the Mac mini. Start services only in an active
plan task that expressly authorizes them, and report the exact command and
smoke URL.

## Historical Decisions

- `ADR-001-langgraph-native-routedeck.md`: historical rationale for not
  reinventing execution graphs; superseded for required LangGraph/compiler
  direction.
- `ADR-002-two-adoption-modes-one-kernel.md`: historical runtime-neutral ideas;
  superseded for first-release multi-mode/durability requirements.
- `ADR-003-agentic-interaction-state-governor.md`: historical rationale for
  interaction governance and host-owned product-tool execution; superseded by
  ADR-004 for sequencing and approved runtime scope.
- `docs/superpowers/plans/2026-07-10-routedeck-full-stack-framework-refactor.md`:
  retired and must not be executed.
