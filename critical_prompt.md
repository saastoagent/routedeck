# Critical Prompt - RouteDeck

The controlling decision is
[ADR-004](./decisions/ADR-004-routedeck-medusa-consumer-driven-runtime.md),
which activates the approved
[RouteDeck and Medusa buyer-agent design](./docs/superpowers/specs/2026-07-11-routedeck-medusa-agent-design.md)
and its
[consumer-driven implementation plan](./docs/superpowers/plans/2026-07-11-routedeck-medusa-agent-implementation.md).

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

Use real product IDs, matching working Corpus behavior. Do not replace product
entity IDs with opaque RouteDeck identifiers.

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

## Consumer-Driven Medusa Rule

The standalone Medusa guest-buyer agent is the first consumer of the approved
runtime. Work advances through vertical slices: add only the RouteDeck
capability immediately required by the matching Medusa behavior, then prove
both sides. A framework-only test result never completes a slice.

Medusa owns Store API transport, commerce truth, feature handlers/providers/
guards, LangGraph prompt/model behavior, and product surfaces. RouteDeck owns
product-neutral feature composition, interaction/session state, supervision,
persistence, transport, and frontend synchronization. RouteDeck contains no
Medusa endpoint templates or commerce behavior.

Corpus remains an existing integration and historical behavior reference. It
does not control the active implementation sequence.

## Runtime Neutrality

RouteDeck core must not require LangGraph. The approved optional
`routedeck_langgraph` middleware translates model/tool calls into the same
supervised operation runner used by UI actions. The standalone Medusa product
owns its prompt, model, and LangGraph graph. Product handlers still execute
through the injected host executor; RouteDeck never invokes commerce behavior
directly.

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

## Approved Runtime And Portability Scope

ADR-004 authorizes immutable feature composition, one supervised operation
runner, durable RouteDeck session/conversation/navigation/review/operation/
projection/event state, the generic FastAPI/SSE and SQLAlchemy persistence adapters, optional
LangGraph middleware, headless/React packages, and the standalone Medusa buyer
agent.

This approval does not move product tool execution or Medusa business logic
into RouteDeck. The host executor remains injected. Product paths use real
local Medusa data and fail visibly when required data, credentials,
dependencies, guards, or invariants are missing. Fixtures, canned responses,
heuristic routing, and silent fallback behavior remain prohibited outside
explicitly isolated tests.

## Stop Conditions

Stop and re-plan if:

- a change contradicts ADR-004 or the approved design
- an agent can invoke an application-semantic tool without RouteDeck oversight
- RouteDeck begins invoking product tools itself
- an ID not present in the current tool-specific allowlist reaches the host tool
  runner
- hidden entities, credentials, route operations, or diagnostics enter normal
  agent context
- product code must rebuild generic RouteDeck context, navigation, surfaces,
  feedback, or SSE behavior
- a RouteDeck change breaks an active Corpus route or browser flow
- a framework capability has no matching Medusa consumer slice or crosses the
  approved framework/product boundary
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
  `decisions/ADR-004-routedeck-medusa-consumer-driven-runtime.md`
- Approved design:
  `docs/superpowers/specs/2026-07-11-routedeck-medusa-agent-design.md`
- Active plan:
  `docs/superpowers/plans/2026-07-11-routedeck-medusa-agent-implementation.md`
- Current state: `context.md`
- Existing schema authority: `routedeck_core/models.py`
- Existing feature reference: `docs/route-deck-reference.md`, subject to ADR-004
- Historical interaction-governance rationale:
  `decisions/ADR-003-agentic-interaction-state-governor.md`
- Retired plan:
  `docs/superpowers/plans/2026-07-10-routedeck-full-stack-framework-refactor.md`

Implementation and verification run only on the local Windows development
machine. Do not probe, select, or fall back to the Mac mini. Start services only
when the active plan task expressly authorizes them, and report the exact
command and smoke URL.
