# ADR-003: RouteDeck Governs Agentic Interaction State

Status: Accepted
Date: 2026-07-10

This decision supersedes the compiler-first and durability-first portions of
ADR-001, ADR-002, and the retired 2026-07-10 full-stack framework refactor
plan. Those documents remain useful history, but this ADR controls current
RouteDeck product identity, first-release scope, and Corpus migration.

## Context

Agent-powered applications are difficult to keep grounded. An agent can see too
much context, call a tool that is not valid in the current application state,
invent or reuse an identifier, bypass a review step, lose track of the active
surface, or describe a state change that never happened.

Corpus already demonstrated a working answer to much of this problem:

- a navgraph representing the application's interaction states and transitions
- planning context limited to the current node, surface, visible entities, and
  legal operations
- real identifiers bound to visible selections
- dynamic guards, blocked-action feedback, reviews, and recovery
- active, peer, detail, form, and review surfaces
- deep links and back, forward, cancel, and surface navigation
- tool-result evidence, diagnostics, and SSE-driven UI updates

The failure was architectural rather than conceptual. These generic mechanics
became tightly integrated with Corpus. A later attempt then expanded RouteDeck
horizontally into a compiler, authoritative execution runtime, durable event
backend, and multiple adoption modes before preserving one working Corpus
vertical flow. Its public dispatch contract changed without migrating Corpus,
breaking the active product path.

## Decision

RouteDeck is the state-management and interaction-governance layer for agentic
applications.

Its primary promise is:

> Give an agent only the application context it currently needs, supervise
> every application-semantic tool call, and keep navigation, identities,
> guards, surfaces, results, and UI state coherent.

RouteDeck is not the agent, model, graph engine, tool executor, product database,
or authentication system.

## The Navgraph

The navgraph is the interaction map of the agentic application. It is closer to
an application sitemap plus guarded capabilities than to an agent execution
graph.

It declares:

- user-facing interaction nodes
- reachable transitions
- tools/operations available from each node
- tool argument requirements and review posture
- surfaces and their placement
- deep-link and navigation behavior
- recovery paths

Runtime providers supply changing facts such as the current actor, visible
records, readiness, permissions, tool results, and surface props. RouteDeck uses
those facts to determine the current projection; they do not create a second
interaction map.

## Tool-Call Supervision

Every application-semantic tool call, including reads and writes, crosses the
RouteDeck supervision boundary.

```text
agent proposes a tool call
  -> RouteDeck checks current session/navgraph state
  -> RouteDeck checks tool availability, arguments, real-ID allowlists,
     product-supplied guards, and review requirements
  -> RouteDeck returns allowed, blocked, needs_input, or requires_review
     with structured feedback
  -> the host agent runtime invokes the product-owned tool only when allowed
  -> the host reports the result or failure to RouteDeck
  -> RouteDeck updates interaction/session state, context, surfaces, events,
     and feedback
```

RouteDeck does not invoke the product tool. It oversees the call before and
after execution. Official integrations must make this gate the normal,
unavoidable tool path; an agent runtime that deliberately bypasses the
integration is outside RouteDeck's guarantee.

The host application supplies trusted actor/context facts and guard functions.
RouteDeck evaluates and enforces them at the agent interaction boundary.
Product code continues to own domain correctness and the tool's actual side
effects.

## Real Identifier Grounding

The first release uses real product identifiers, matching working Corpus
behavior. It does not introduce opaque RouteDeck identifiers.

RouteDeck may expose a real ID to the agent only when a trusted provider places
that record in the current projected context. A proposed ID must match the
current allowlist for that specific tool/operation and session state. Fabricated,
stale, hidden, or currently ineligible IDs are rejected with useful feedback
and are never forwarded to the tool runner.

This preserves direct product API compatibility while preventing the agent from
treating arbitrary strings as trusted application identity. Public response
rendering continues to redact internal IDs when the product experience should
not reveal them.

## State Ownership

RouteDeck owns interaction and session state needed to keep an agentic
application coherent:

- current navgraph location and navigation history
- active and available surfaces
- visible selections and current real-ID allowlists
- legal and blocked tools/operations plus feedback
- needs-input and review state
- relevant tool-result summaries/references
- projection/version information already required by Corpus behavior
- SSE-visible interaction status and updates
- read-only diagnostics and guard explanations

Product systems remain authoritative for domain records, authentication,
business data, tool implementations, external side effects, prompts, model
calls, and private agent-runtime state.

## Scoped Agent Context

RouteDeck constructs the structured, minimal context supplied to the agent. It
contains only what is relevant now, such as:

- current node and active surface
- current product/workspace summary
- visible selectable entities with real IDs and allowed tool bindings
- legal product tools with accepted arguments and readiness
- allowed surface choices
- relevant recent tool-result summaries

Hidden route operations, inaccessible entities, credentials, private
diagnostics, and unrelated application state stay out of normal agent context.
Product code continues to own prompts, personality, and response wording.

## Surfaces, Navigation, Events, And Clients

Capabilities already demonstrated by Corpus belong in RouteDeck's reusable
interaction layer:

- active, frame, peer, detail, form, and review surface mechanics
- surface selection and dirty-surface coordination
- surface affordance events and tool/selection bindings
- back, forward, cancel, recovery, and product-owned deep links
- typed interaction events and existing SSE handling
- frontend projection/store synchronization
- tool-result and projection updates
- public/private event and diagnostics separation

Products own the actual surface components, product language, domain data, and
visual design.

## Runtime Neutrality

The RouteDeck core must not require LangGraph or any other agent runtime.
Runtime neutrality is an interface constraint, not a requirement to build many
adapters now.

The first extraction uses the existing Corpus planner/agent driver through a
small injected boundary. Later, a Medusa agent proves that another agent runtime
can use the same RouteDeck context, tool supervision, surfaces, and events.
LangGraph may receive an official adapter later, but a compiler and LangGraph
dependency are not part of the first extraction.

## Declarative Authoring

Developers describe the interaction map once: nodes, transitions, available
tools, required selections, surfaces, deep links, and recovery behavior.
RouteDeck applies that declaration consistently to the agent, backend
supervision boundary, SSE projection, and frontend state.

Ordinary product functions provide dynamic facts and behavior: load visible
records, calculate guards, populate surfaces, run tools in the host runtime,
and interpret results. Developers should not rebuild generic navigation,
surface lifecycle, context filtering, argument allowlisting, feedback, or SSE
framing inside each product.

## First-Release Scope

The first RouteDeck extraction is bounded by behavior already demonstrated in
working Corpus. Corpus feature parity is the acceptance target.

Included:

- navgraph and guarded navigation
- scoped agent context
- real-ID allowlisting against current visible entities
- supervision of every application-semantic tool call
- legal/blocked tool feedback, needs-input, and review states
- existing surface, selection, deep-link, recovery, diagnostics, and SSE
  behavior
- interaction and session state needed by those features

Explicitly deferred unless separately approved:

- a RouteDeck-owned product tool executor
- opaque identifier infrastructure
- a LangGraph compiler or required LangGraph dependency
- new SQLite/event/outbox durability infrastructure
- stronger replay or idempotency systems not already required by Corpus
- multiple adoption modes and their conformance framework
- independent example projects

The Medusa agent is the later portability proof after Corpus parity is stable.

## Migration Rule

Migration is vertical and parity-first:

1. Preserve the current Corpus behavior as the feature baseline.
2. Extract one existing interaction capability at a time into RouteDeck.
3. Keep Corpus callers compatible throughout each slice.
4. Prove backend behavior and the matching browser flow before continuing.
5. Remove duplicate Corpus mechanics only after call-site and behavior proof.

A RouteDeck-internal test count is not sufficient evidence. Each slice must
leave Corpus green and usable. Missing real data, dependencies, integrations,
or invariants fail loudly; no synthetic product fallback may stand in for the
working product behavior.

## Consequences

- RouteDeck's identity becomes smaller and clearer: agentic interaction state
  and tool-call governance.
- Corpus remains the initial behavioral oracle even where its current ownership
  is wrong.
- LangGraph is optional and downstream of the core interaction contract.
- Existing working features move before new infrastructure is considered.
- RouteDeck can block a call and explain why without owning or executing the
  product tool.
- Real identifiers remain easy to integrate while becoming state-scoped and
  operation-scoped.
- Later portability is proven through Medusa only after Corpus parity.
