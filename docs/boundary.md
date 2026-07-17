# RouteDeck Boundary

Status: current product/framework boundary
Date: 2026-07-17

RouteDeck owns generic interaction state and supervision. A consuming product
owns domain truth, agent behavior, and side effects.

| RouteDeck owns | Product owns |
| --- | --- |
| `Application`/`Feature` compilation and navgraph validation | Feature declarations and business meaning |
| Canonical sessions, conversation, navigation, review, surfaces, and events | Domain records, APIs, wire formats, and source-of-truth reads |
| One operation runner and typed allow/block/input/review/recovery behavior | Product handler execution and external side effects |
| Scoped context, private bindings, opaque handles, guards, and projection | Trusted provider facts and product policy |
| Runtime construction, persistence ports, FastAPI/SSE, browser synchronization | Deployment host, authentication, user/session authorization |
| Generic LangGraph event translation and tool supervision | Prompts, models, graph topology, policy, personality, and wording |
| Product-neutral React primitives and read-only diagnostics | Product components, copy, styling, and affordance composition |

## Execution Boundary

```text
UI or agent proposes a declared operation
  -> RouteDeck validates current session/context/guard/review/handle scope
  -> product handler executes only when allowed
  -> product returns a typed outcome/failure and delivery evidence
  -> RouteDeck commits state, projection, and ordered events
```

RouteDeck coordinates the call but does not become the product executor. A
semantic tool call that bypasses this path is outside the RouteDeck guarantee.

## Graph Boundary

The RouteDeck navgraph describes durable product locations, legal operations,
surfaces, deep links, and recovery. A LangGraph graph describes private
model/tool orchestration. RouteDeck does not mirror or compile one into the
other.

## Identifier And Data Boundary

The product owns real IDs. RouteDeck stores them only in classified private
bindings and exposes scoped opaque handles. Private IDs, form values,
credentials, hidden operations, and diagnostics never enter normal browser or
model context.

## Session Boundary

RouteDeck owns the state of a selected session. The consumer owns users,
tenants, session listings, and authorization. The Medusa reference currently
uses one HTTP-only guest cookie; an authenticated multi-session resolver is not
implemented.

## Failure Boundary

Missing data, models, adapters, bindings, guards, permissions, or invariants
fail visibly. RouteDeck and its reference app do not substitute fixtures,
canned assistant text, heuristic routing, alternate providers, or silent
fallback state.
