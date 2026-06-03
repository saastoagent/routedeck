# Critical Prompt - RouteDeck

RouteDeck is a reusable framework for graph-backed agentic UI state. It lets
products expose dynamic surfaces, navgraph location, capabilities, dispatch,
diagnostics, and client stores without letting UI or chat own product truth.

The canonical framework reference is `docs/route-deck-reference.md`. Start there
before changing framework language, schema meaning, runtime contracts, surfaces,
or product examples.

## North Star

RouteDeck's spine is:

```text
Product graph truth
  -> RouteDeck navgraph
  -> capability contract
  -> RouteDeck projection
  -> surfaces, chat, automation, diagnostics
  -> affordance event or agent-selected capability request
  -> RouteDeck dispatch
  -> graph commit, rejection, review, or recovery
  -> semantic observation and next projection
```

RouteDeck owns reusable projection, navigation, navgraph, capability, dispatch,
surface, diagnostics, introspection, event, and client-store contracts. Products
own domain vocabulary, prompts, planning context construction, product agents,
product runtimes, domain data, auth, persistence, business policy, product UI
copy, LLM calls, semantic observations, and side effects.

## Non-Negotiable Boundaries

- Product graph truth stays in the product graph or product runtime.
- RouteDeck projection is output, not the source of graph behavior.
- Surfaces present capabilities through affordances; they do not mutate graph
  state directly.
- Anything semantic that can be done from a surface must also be available to
  chat through product-agent planning context.
- Product agents consume product-owned planning context derived from RouteDeck
  projection; RouteDeck does not own prompts, model calls, or phrase routing.
- Internal `route.*` operations are framework/runtime plumbing and stay hidden
  from ordinary product UI and product-agent planning context.
- Product-specific APIs stay product-owned. Do not turn `/api/routedeck/*` into
  a Medusa, SaaStoAgent, cart, checkout, admin, or product-domain API.
- Do not add deterministic command routers as a substitute for agent planning
  context, entity binding, and runtime validation.

## Current Architecture Posture

- Schema authority: `routedeck_core/models.py`
- Framework reference: `docs/route-deck-reference.md`
- Backend contracts: `routedeck_core/`
- Optional LangGraph adapter: `routedeck_langgraph/`
- React client package: `react/src/`
- Active product reference example: `examples/medusa-agent/`
- Source ownership map: `architecture/code-map.md`
- Validation anchors: `test_index/README.md` and executable tests

## Active Warning

The RouteDeck reference is ahead of parts of the derived codebase. Treat current
core models, React types/store, and `examples/medusa-agent` implementation as
downstream alignment targets, not final authority, when they conflict with
`docs/route-deck-reference.md`.

## Stop Conditions

Stop and re-plan if:

- a change contradicts `docs/route-deck-reference.md`
- framework code starts owning product prompts, product agents, or domain APIs
- a surface-only capability cannot also be represented in chat planning context
- source ownership is unclear in `architecture/code-map.md`
- implementation would overwrite unrelated user work
