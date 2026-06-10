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
- Visual navgraph surfaces are read-only orientation/inspection UI. Selecting a
  graph node may only change local inspection focus; it must not dispatch,
  navigate, mutate graph state, or change the browser URL.
- Product action chips come from product-curated projected capabilities,
  operations, affordances, or agent proposals. They do not come from clickable
  navgraph nodes.
- Product action chips belong to the product chat/assistant experience, such as
  Corpus-style quick actions attached to assistant turns or the active composer
  context. Do not render them as navgraph artifacts.
- Agent-first reference apps should open with an assistant chat turn that carries
  starter action chips when legal actions exist. Do not replace the chat with an
  empty-state panel, landing page, debugger, or graph-first placeholder.
- Do not render `legal_operations` wholesale as chips. Hide blocked,
  hidden/internal, unbound selector/form, and normal current-node no-op
  operations unless the product intentionally presents a refresh/reload action.
- Product surfaces and navgraph/inspector surfaces must stay separate. In
  agent-centric apps, the active product surface belongs inside the chat or
  workbench stream, Corpus-style, not as a detached product side panel. Product
  cards, home CTAs, cart buttons, and variant controls emit declared surface
  affordance events; navgraph selection only changes local inspection focus.
- Address-bar deeplinks are product-owned URL codecs. Follow the Corpus pattern:
  graph location belongs in product path segments, and query params are reserved
  for optional surface/presentation state or legacy compatibility. Do not make
  `?rd_node=...` the canonical public URL for new product examples.
- Internal `route.*` operations are never ordinary product chips.
- Anything semantic that can be done from a surface must also be available to
  chat through product-agent planning context.
- Once a product projection or product surface is visible, a chat turn that
  claims to browse, open, select, compare, or otherwise change the product
  surface must cross the same product-owned RouteDeck runtime boundary as the
  equivalent surface affordance. Assistant prose alone is not a state update.
- Read-only means no product side effects such as cart, checkout, payment,
  shipping, admin, or irreversible writes. It does not prohibit guarded read
  transitions, surface changes, projection refreshes, or canonical path updates
  that are accepted by the product runtime.
- Product agents consume product-owned planning context derived from RouteDeck
  projection; RouteDeck does not own prompts, model calls, or phrase routing.
- Public chat must not invent product facts. Product names, prices, variants,
  colors, sizes, availability, cart contents, and current surface state must be
  grounded in projection/planning context or a product tool result; otherwise the
  agent asks for setup or says the fact is unavailable.
- Internal `route.*` operations are framework/runtime plumbing and stay hidden
  from ordinary product UI and product-agent planning context.
- Product-agent SSE, RouteDeck state SSE, and diagnostics streams are separate
  channels. Do not mix assistant text, projection updates, and diagnostic traces
  into one public semantic stream.
- Diagnostics are read-only explanation surfaces. They must not become public
  chat, ordinary product UI, product action chip sources, dispatch controls, or
  substitutes for the product runtime.
- `RouteDeckStore` mirrors runtime state for React clients. It must not become
  graph truth, invent capabilities, bypass dispatch validation, or store product
  side effects.
- Product-specific APIs stay product-owned. Do not turn `/api/routedeck/*` into
  a Medusa, SaaStoAgent, cart, checkout, admin, or product-domain API.
- Do not add deterministic command routers as a substitute for agent planning
  context, entity binding, and runtime validation.
- When implementing a visible Medusa Agent slice, do not satisfy it by creating
  a separate product-neutral RouteDeck demo, dashboard, or graph-first app.
  Medusa visible work stays in `examples/medusa-agent/` and must preserve the
  chat-first product-agent experience while RouteDeck operates underneath it.
- Use subagents for RouteDeck/Medusa implementation slices: one reference or
  vision reviewer and one drift/code reviewer at minimum before readiness is
  claimed.

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
- navgraph UI mutates graph state, dispatches, navigates, or changes route state
- framework code starts owning product prompts, product agents, or domain APIs
- a surface-only capability cannot also be represented in chat planning context
- a visible product surface is called usable before an equivalent chat request
  can drive the same projection/runtime boundary
- assistant chat answers product facts that are absent from projection,
  planning context, or a product tool result
- read-only is interpreted as "no guarded read transition" instead of "no
  product side effect"
- product chips expose internal `route.*` operations or hidden runtime plumbing
- product chips drift out of the chat/assistant experience into navgraph UI
- product-agent text streams, RouteDeck state streams, or diagnostics streams
  are collapsed into one public stream
- diagnostics become public chat, default product UI, a chip source, or a
  mutation control
- `RouteDeckStore` starts inventing graph truth, capabilities, product side
  effects, or dispatch outcomes outside the runtime
- an agent reference app starts from an empty-state panel instead of an assistant
  chat turn with starter chips
- product surfaces and navgraph/inspector UI are merged so product clicks look
  like graph navigation
- an agent-centric product surface is rendered as a detached side panel instead
  of being embedded in the chat/workbench stream
- a new product example exposes query-only `?rd_node=...` links as the canonical
  copyable browser deeplink instead of a product-owned path codec
- product chips render current-node no-op operations as ordinary next actions
- source ownership is unclear in `architecture/code-map.md`
- implementation would overwrite unrelated user work
- a Medusa Agent slice is being reinterpreted as a standalone product-neutral
  RouteDeck example or debugger
- a slice is called ready before browser behavior and code are compared against
  the Medusa vision and anti-drift tests
