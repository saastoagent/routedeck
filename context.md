# RouteDeck Context

Last updated: 2026-07-10
Status: The agentic interaction-state vision is locked in ADR-003. The previous
compiler/durability-first refactor plan is retired. No replacement
implementation plan is active yet.

## Start Here

1. [Critical prompt](./critical_prompt.md)
2. [ADR-003: RouteDeck Governs Agentic Interaction State](./decisions/ADR-003-agentic-interaction-state-governor.md)
3. [Current context](./context.md)
4. [Decision index](./decisions/README.md)
5. [RouteDeck reference](./docs/route-deck-reference.md) for existing feature vocabulary and payloads,
   subject to ADR-003 where older target language conflicts
6. [Architecture code map](./architecture/code-map.md)
7. [Test index](./test_index/README.md)
8. [SaaStoAgent/Corpus context](../saastoagent-v0.1/context.md) for the current Corpus feature baseline

Do not resume the
[retired full-stack refactor plan](./docs/superpowers/plans/2026-07-10-routedeck-full-stack-framework-refactor.md).
It is retained as historical material only.

## Pre-Implementation Review Gate

> **Temporary gate — remove this entire section when implementation begins.**
> The user must thoroughly review and approve
> [ADR-003](./decisions/ADR-003-agentic-interaction-state-governor.md) before
> any RouteDeck or Corpus implementation starts. Until that review is complete,
> keep work in documentation/analysis only.

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

## Corpus Is The First Feature Baseline

Working Corpus behavior defines the first extraction boundary even where the
current code ownership is wrong. Preserve:

- the 26-node/40-operation navgraph and guarded reachability
- scoped planning context: current node/surface, active SaaS Agent, visible
  entities, surface choices, and legal product operations
- authentication/membership/readiness/pending-review guards and feedback
- real-ID selections sourced from visible product surfaces
- active, frame, peer, detail, form, and review surfaces
- surface selection and dirty-surface handling
- back, forward, cancel, recovery, and product-owned deep links
- tool result/evidence handling and result-review flows
- existing Corpus SSE behavior and frontend projection updates
- diagnostics and public/internal information separation

RouteDeck-internal tests do not prove a slice complete. Corpus backend behavior
and the matching browser flow must remain green after every extraction slice.

## Current Implementation Reality

Already present:

- product-neutral manifest, navgraph, projection, operation, context-lens,
  entity, surface, dispatch, event, and diagnostics contracts
- generic navigation, operation policy, projection, review, and surface helpers
- an optional `routedeck_langgraph` package
- React provider/store/hooks and product surface integration helpers
- a feature-rich Corpus runtime that demonstrates the intended behavior but
  still contains generic RouteDeck mechanics

Known gaps relative to ADR-003:

- Corpus subclasses and extends RouteDeck instead of consuming a small composed
  interaction kernel
- tool supervision is not yet expressed as a reusable before/after boundary
  for every application-semantic tool call
- real IDs are exposed from visible surfaces, but generic operation-scoped
  allowlist validation is not yet consistently enforced
- generic context filtering, surfaces, navigation, SSE framing, diagnostics,
  and result observation remain mixed into Corpus
- the current docs/reference still contain historical Full Flow, compiler,
  durability, and multi-mode language; ADR-003 controls when they conflict

## Explicitly Deferred

Do not add these to the first extraction without a new user-approved decision:

- a RouteDeck-owned tool executor
- opaque identifier infrastructure
- a required LangGraph dependency or compiler
- new SQLite session/event/outbox infrastructure
- replay/idempotency systems not already needed by Corpus behavior
- multiple adoption modes and conformance infrastructure
- independent example projects

The Medusa agent is a later portability proof after Corpus parity is stable.

Preserve the Medusa **2026-06-10 gap audit** and its
**chat-to-projection convergence** rule as historical acceptance evidence. Any
later Medusa portability proof must still require a claimed interaction change
to cross the supervised runtime boundary and produce the matching projection
update.

## Migration And Validation Rule

1. Establish the current working Corpus behavior as the executable baseline.
2. Extract one already-working capability vertically.
3. Keep the active Corpus caller contract compatible.
4. Run focused backend tests and the matching browser flow.
5. Remove duplicate Corpus code only after call-site and behavior proof.

No service or browser run is authorized by this context alone. Before runtime
verification, ask whether to use local, Mac mini LAN, or Mac mini Tailscale and
report the exact command and smoke URL.

## Historical Decisions

- `ADR-001-langgraph-native-routedeck.md`: historical rationale for not
  reinventing execution graphs; superseded for required LangGraph/compiler
  direction.
- `ADR-002-two-adoption-modes-one-kernel.md`: historical runtime-neutral ideas;
  superseded for first-release multi-mode/durability requirements.
- `docs/superpowers/plans/2026-07-10-routedeck-full-stack-framework-refactor.md`:
  retired and must not be executed.
