# Critical Prompt - RouteDeck

The controlling decision is
[ADR-003](./decisions/ADR-003-agentic-interaction-state-governor.md).

RouteDeck is state management and interaction governance for agentic
applications. It gives an agent only the context it currently needs, supervises
every application-semantic tool call, and keeps navigation, real identifiers,
guards, surfaces, tool results, SSE updates, and frontend state coherent.

RouteDeck is not the agent, model, graph engine, product tool executor, product
database, or authentication system.

## North Star

```text
trusted product facts + navgraph declaration
  -> RouteDeck interaction/session projection
  -> scoped agent context with visible real IDs and legal tools
  -> agent proposes a tool call
  -> RouteDeck allows, blocks, requests input, or requires review
  -> host agent runtime executes an allowed product tool
  -> host reports the result/failure to RouteDeck
  -> RouteDeck updates context, surfaces, events, feedback, and client state
```

The navgraph is the agentic application's interaction map: user-facing states,
reachable transitions, tools, surfaces, deep links, and recovery paths. It is
not the agent's private execution graph.

## Ownership

RouteDeck owns reusable:

- interaction and session state
- navgraph validation and guarded navigation
- scoped planning/context projection
- legal/blocked tool metadata and structured feedback
- current-operation real-ID allowlists
- before/after tool-call supervision
- needs-input and review interaction state
- active/frame/peer/detail/form/review surface mechanics
- surface selection, affordance, and dirty-state coordination
- back/forward/cancel/recovery and product-owned deep-link integration
- relevant tool-result observation and projection updates
- existing typed interaction events and SSE framing demonstrated by Corpus
- frontend projection/store synchronization
- read-only diagnostics and public/private information separation

Products own:

- domain records and business truth
- authentication and trusted actor facts
- product-supplied guard functions and policy facts
- prompts, model calls, agent personality, and response wording
- product tool implementations and actual tool invocation
- external side effects
- product surface components, props, copy, and visual design
- private agent-runtime state

RouteDeck evaluates and enforces product-supplied guards before the host runtime
invokes a tool. Product code remains responsible for the tool's domain
correctness and effects.

## Tool Supervision

Every application-semantic read and write tool call crosses RouteDeck.
RouteDeck does not invoke the tool. It returns one of:

- `allowed`, with validated/normalized arguments
- `blocked`, with a reason and currently available alternatives
- `needs_input`, with missing fields
- `requires_review`, with review state/surface information

The host integration invokes only allowed tools and reports every result or
failure back through RouteDeck. An integration that deliberately bypasses this
gate is outside the RouteDeck guarantee.

## Real Identifier Rule

Use real product IDs, matching working Corpus behavior. Do not add opaque
RouteDeck IDs to the first extraction.

A trusted product provider places visible records and real IDs into the current
projection. RouteDeck accepts an agent-supplied ID only when it is allowed for
the requested tool in the current session/navgraph state. Fabricated, stale,
hidden, cross-context, or currently ineligible IDs are blocked before the host
tool runner sees them.

Public assistant responses must still redact internal IDs when the product
experience should not reveal them.

## Declarative Authoring

Developers describe the interaction map once: nodes, transitions, available
tools, required selections, surfaces, deep links, and recovery behavior.

Ordinary product functions supply changing facts and behavior: load visible
records, calculate guards, populate product surfaces, run tools in the host
runtime, and interpret results. Products must not recreate generic context
filtering, navigation history, surface lifecycle, ID allowlisting, feedback, or
SSE framing.

## Corpus Parity Rule

Working Corpus behavior is the first RouteDeck feature oracle even where its
current code ownership is wrong.

The first extraction is limited to capabilities Corpus already demonstrates:

- 26 interaction nodes and 40 operations
- guarded reachability and recovery
- scoped planning context
- visible real-ID selections
- legal/blocked operations and review flows
- active and alternate product surfaces
- deep links and navigation history
- tool-result evidence and result review
- existing Corpus SSE and frontend projection behavior
- diagnostics and internal/public redaction

Do not add speculative framework infrastructure during this extraction. A
RouteDeck-only test count is not completion; every slice must preserve the
matching Corpus backend and browser behavior.

## Runtime Neutrality

RouteDeck core must not require LangGraph. The first integration uses the
existing Corpus planner/agent driver through a small injected boundary.
Runtime-neutral means RouteDeck does not know how the agent made its decision;
it does not mean building many adapters now.

The Medusa agent is the later portability proof. A LangGraph adapter or compiler
requires a separate user-approved decision.

## Non-Negotiable Product Rules

- LLMs do not patch application state directly; they request supervised tools.
- Assistant prose alone is not a state update.
- Public chat must not invent product facts.
- Anything semantic that a surface can do must also be representable to the
  agent through current scoped context.
- A chat statement is not a state change. Browse/open/select/compare/tool claims
  must cross the same supervised interaction boundary as the equivalent UI
  affordance and produce the matching projection update.
- Hidden `route.*` operations stay out of normal product UI and agent context.
- Legal tools are not rendered wholesale as one-click actions. Form, selector,
  review, hidden, and blocked posture must be respected.
- Product facts must come from current projection/context or a reported product
  tool result. The agent must not invent products, prices, variants,
  availability, selections, permissions, or current surface state.
- Product surfaces are separate from navgraph diagnostics. Surface controls
  request supervised tools; diagnostic navgraph selection is read-only.
- Visual navgraph surfaces are read-only orientation/inspection UI. Selecting a
  graph node must not dispatch, navigate, mutate graph state, or change the
  browser URL.
- Product action chips come from product-curated projected capabilities,
  operations, affordances, or agent proposals.
- Product action chips belong to the product chat/assistant experience, not the
  navgraph.
- Agent-first reference apps should open with an assistant chat turn when legal
  starter actions exist.
- Internal `route.*` operations are never ordinary product chips.
- Do not render `legal_operations` wholesale as chips.
- Product surfaces and navgraph/inspector surfaces must stay separate. In
  agent-centric apps, the active product surface belongs inside the chat or
  workbench stream, not in a detached side panel.
- Address-bar deeplinks are product-owned URL codecs. Do not make
  `?rd_node=...` the canonical public URL for a new product.
- Diagnostics never become public chat, a product action source, or a mutation
  control.
- Assistant, interaction-state, tool/surface, and diagnostic events retain
  explicit semantic and visibility separation even when transported through
  SSE.
- RouteDeck frontend state mirrors the supervised runtime; it does not invent
  legal tools, results, or product truth.
- Product-specific APIs and tool behavior stay product-owned.
- Missing real data, dependencies, guards, tool runners, or invariants fail
  loudly. No fake, canned, heuristic, or silent fallback may make a product
  path look grounded.

## Explicitly Deferred

Unless separately approved, the first extraction does not include:

- RouteDeck-owned product tool execution
- opaque identifier infrastructure
- a required LangGraph dependency or compiler
- new SQLite/event/outbox durability
- replay/idempotency beyond existing Corpus behavior
- Full Flow/Core Integration product modes
- independent example projects

## Stop Conditions

Stop and re-plan if:

- a change contradicts ADR-003
- an agent can invoke an application-semantic tool without RouteDeck oversight
- RouteDeck begins invoking product tools itself
- an ID not present in the current tool-specific allowlist reaches the host tool
  runner
- hidden entities, credentials, route operations, or diagnostics enter normal
  agent context
- product code must rebuild generic RouteDeck context, navigation, surfaces,
  feedback, or SSE behavior
- a RouteDeck change breaks an active Corpus route or browser flow
- a slice adds compiler, durability, adapter, or example scope not demonstrated
  by Corpus and separately approved
- product chips render current-node no-op operations as ordinary next actions
- an agent reference app starts from an empty-state panel instead of an
  assistant chat turn
- an agent-centric surface becomes a detached side panel instead of being
  embedded in the chat/workbench stream
- a new product example exposes query-only `?rd_node=...` links as the canonical
  copyable browser deeplink
- assistant prose is accepted as state change without matching supervised
  execution and projection evidence
- implementation would overwrite unrelated user work

## Current Authority

- Controlling decision:
  `decisions/ADR-003-agentic-interaction-state-governor.md`
- Current state: `context.md`
- Existing schema authority: `routedeck_core/models.py`
- Existing feature reference: `docs/route-deck-reference.md`, subject to ADR-003
- Corpus behavioral baseline: `../saastoagent-v0.1/context.md`
- Retired plan:
  `docs/superpowers/plans/2026-07-10-routedeck-full-stack-framework-refactor.md`

Before runtime/browser verification, ask whether to use local, Mac mini LAN, or
Mac mini Tailscale and report the exact command and smoke URL.
