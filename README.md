# RouteDeck

RouteDeck is a state and interaction framework for agentic applications. A
product declares its nodes, routes, operations, providers, guards, surfaces,
and transitions; RouteDeck compiles those declarations into one authoritative
backend contract and one typed frontend contract.

The framework owns runtime assembly, session state, durable supervision,
review, projection, events, private-form transport, deep links, exact history,
generic user/assistant conversation driving, and React state synchronization.
The consuming application owns product behavior: declarations and bindings,
prompts, models and graph topology, API clients, domain validation, side
effects, market facts, readiness, copy, and visual components.

The standalone app in [`examples/medusa-agent`](examples/medusa-agent/README.md)
is the reference consumer. It implements a real local Medusa guest-buyer flow
without putting commerce code in RouteDeck.

## Packages

- `routedeck_core` - immutable application contracts, compilation, canonical
  sessions, operation supervision, projection, navigation, ports, and the
  framework-owned runtime/services builder.
- `routedeck_sqlalchemy` - fenced SQLAlchemy ORM persistence for SQLite and
  PostgreSQL, durable events, private blobs, sensitive-data encryption, and a
  fail-closed runtime opener.
- `routedeck_fastapi` - one runtime-derived `/api/routedeck/*` session,
  conversation, assistant-turn, dispatch, navigation, review, private-form,
  inspection, and SSE transport.
- `routedeck_langgraph` - optional generic graph driver, conversation
  extraction, middleware, and tool wrapping over application-owned graphs.
- `routedeck_testing` - Python conformance helpers and explicitly test-only
  scripted models.
- `@routedeck/core` - generated contracts, user/assistant conversation and
  HTTP/SSE clients, authoritative client store, route codec, browser-history
  adapter, and private-form state.
- `@routedeck/react` - provider, hooks, surface host, navigation, review,
  private-form, status, inspector primitives, and named conversation
  presentation actions.
- `@routedeck/testing` - frontend harnesses and factories for tests.

## Boundary

RouteDeck never calls Medusa and never knows about products, carts, shipping,
payments, or orders. The Medusa app keeps those concerns in:

- `medusa_agent/features/*` for feature declarations and operation-centric
  business slices;
- `medusa_agent/medusa/client` for the typed Store API port, HTTP adapter, wire
  models, delivery evidence, and sanitized failures;
- `medusa_agent/composition.py` for selecting features and the entry node;
- `medusa_agent/bindings.py` for product dependency injection;
- `medusa_agent/agent.py` for product prompts, models, and graph construction;
- `medusa_agent/session.py` for buyer market/session callbacks;
- `medusa_agent/runtime.py` for strict product configuration passed into the
  framework runtime opener;
- product-owned React components under `frontend/src/features`.

Medusa does not construct generic runners, navigation, persistence resources,
FastAPI dependency bundles, or a LangGraph event driver. Its host supplies one
`RouteDeckRuntime` through `create_routedeck_router_from_runtime_provider(...)`
with an explicit host-owned `RouteDeckSessionSelector`, and mounts only product
health/readiness beside the generic route plane.

Every UI affordance and agent tool reaches the same
`RouteDeckOperationRunner`. The browser never calls the Medusa Store API
directly. External writes are journaled, reviewed where declared, and fail
loudly when their outcome cannot be proven.

Session creation, navigation, private-form saves, and chat turns also use a
durable mutation journal. An exact request-ID replay returns the committed
result without repeating product work; the same ID with different input is a
contract error. Clients retain outcome-unknown requests for explicit retry or
abandonment and never silently substitute a new ID.

## Authoring Model

Ordinary feature work is declarative and feature-local:

```python
from routedeck_core.app import Feature
from routedeck_core.contracts.application import (
    Node,
    RouteEntry,
    RouteParameterBinding,
)
from routedeck_core.contracts.navigation import (
    DeepLinkPolicy,
    NodeKind,
    NodeRef,
    Route,
    Transition,
)

product_node = Node(
    id="catalog.product",
    title="Product",
    kind=NodeKind.DETAIL,
    route=Route(
        template="/products/{product_handle}",
        deep_link_policy=DeepLinkPolicy.SHAREABLE,
    ),
    entry=RouteEntry(
        operation=open_product_by_route.ref,
        outcome="opened",
        bindings=(
            RouteParameterBinding(
                parameter="product_handle",
                argument="product_handle",
            ),
        ),
    ),
    operations=(open_product_by_route,),
    outgoing=(
        Transition(
            operation=open_product_by_route.ref,
            outcome="opened",
            target=NodeRef(id="catalog.product"),
        ),
    ),
    surfaces=product_surface_slots,
)

catalog = Feature(namespace="catalog", nodes=(product_node,))
```

Composition selects independently authored features and the entry node.
RouteDeck resolves feature-owned nodes and their outgoing transitions, derives
incoming transitions, validates the complete graph, and compiles it.

`compile_app(...)` validates identifiers, route overlap, exact route-entry
bindings, provider and guard scope, operation outcomes, transitions,
reachability, surface affordances, and recovery declarations. `bind_app(...)`
then requires an exact set of typed async handlers, providers, and guards.
Missing, extra, or incorrectly shaped bindings are configuration errors.

`Surface` declares component identity, lifecycle, public JSON schema, and
operation-backed affordances. Stable surfaces retain canonical public state
across navigation; ephemeral surfaces retain state only while declared by the
current node. A private-form surface adds a server-only
`PrivateFormBinding`; that authorization metadata is not exported to the
browser contract.

See [`docs/route-deck-reference.md`](docs/route-deck-reference.md) for the full
contract and [`docs/using-routedeck.md`](docs/using-routedeck.md) for adoption
guidance.

## LangGraph Relationship

RouteDeck does not turn its navgraph into a LangGraph `StateGraph`. The product
keeps its own `create_agent(...)` or raw `StateGraph` topology.
`RouteDeckMiddleware` supplies a default-deny snapshot of the current public
state and legal operations to each model call, while `RouteDeckToolWrapper`
routes tool calls through the supervised operation runner.

RouteDeck remains the authority for durable conversation turns, session state,
legal operations, review, and projection. LangGraph remains the product-owned
model/tool orchestration layer. RouteDeck exports no topology builder because
creating a second graph from the navgraph would introduce a second state
authority.

RouteDeck also owns the generic graph driver, conversation controller, and
browser lifecycle. A product graph factory supplies explicit `user_message`
and `assistant_initiated` LangGraph streams through
`RouteDeckLangGraphGraphs`; `RouteDeckLangGraphDriverFactory` constructs the
framework driver after runtime services exist. `POST /api/routedeck/chat` and
`POST /api/routedeck/conversation/assistant-turn` share one durable turn lease,
fingerprint, replay, persistence, cancellation, SSE, and interaction handshake.
The assistant path sends no synthetic `HumanMessage`, emits no `user_message`
frame, and rejects tools or review output.

In the browser, `createRouteDeckAgentClient(...)` exposes both stream methods.
React's presentation layer uses named methods for snapshot restore, user
messages, assistant deltas/finalization, review, completion, and failure; it is
not a second canonical RouteDeck store or a public reducer API.

Install the optional integration with the other local framework packages:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[fastapi,langgraph,persistence,testing,dev]"
```

## Local Medusa Quickstart

Local Windows execution is authoritative. Run these commands from this project
directory with the local Docker engine selected:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\demo-stack.ps1 -Action Provision
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\demo-stack.ps1 -Action Up -Services all
```

Open:

- frontend: `http://127.0.0.1:5198`
- agent API: `http://127.0.0.1:8098`
- Medusa: `http://127.0.0.1:9100`

`Provision` creates or validates the protected local fixture and does not
reseed an already valid stack. `Down` stops only this Compose project and
retains its protected volumes:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\demo-stack.ps1 -Action Down
```

`Reset` is intentionally destructive and is not a normal startup step. It
validates the protected project identity and deletion scope before deleting and
reprovisioning the demo fixture.

The API process can expose liveness and non-model RouteDeck endpoints without
model credentials, but full application readiness and the Compose-gated buyer
frontend require an explicit `OPENAI_API_KEY` in
`examples/medusa-agent/.env.local`. There is no fallback model or canned
assistant response. A live-model release smoke has not been claimed for this
checkout unless a release report explicitly records it.

## Validation

Use [`test_index/README.md`](test_index/README.md) for the current commands and
proof boundaries. Generated contracts live under `artifacts/contracts`; they
are outputs of the contract exporter, not hand-authored application state.

Architecture ownership is mapped in
[`architecture/code-map.md`](architecture/code-map.md). The controlling runtime
decision is
[ADR-006](decisions/ADR-006-framework-owned-runtime-and-conversation-boundary.md),
with [ADR-005](decisions/ADR-005-operation-centric-state-and-consumer-structure.md)
retaining its non-superseded structural decisions and
[ADR-004](decisions/ADR-004-routedeck-medusa-consumer-driven-runtime.md)
retaining scope and local-execution authority. Completed plans remain
historical records.
