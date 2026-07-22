# Glossary

| Term | Meaning |
| --- | --- |
| Application | Composition root selecting features and one entry node |
| Binding | Exact async product implementation of a handler, provider, or guard |
| Capability | Inspection/model-context grouping of operations and surfaces; not another execution path |
| Canonical state | Durable RouteDeck session state, as opposed to UI, model, or API-local state |
| Compiled application | Immutable validated navgraph, catalogs, routes, frontend contract, and derived paths |
| Conversation turn | Durable user-authored or assistant-initiated interaction with request identity and terminal state |
| Deep-link policy | Whether a route is `shareable` or `session_bound` |
| Delivery evidence | `not_sent`, `possibly_sent`, or `response_received` for an external write |
| Disposition | Runner decision such as allowed, blocked, needs-input, or review-required |
| Effect | Typed RouteDeck state change returned after allowed product behavior |
| Entity binding | Server-private association between an opaque handle and product ID under a declared scope |
| Event cursor | Ordered durable position used for SSE replay and client convergence |
| Feature | Product-owned namespace containing complete nodes and optional agent policies |
| Frontend contract | Generated product-neutral nodes, transitions, operations, routes, surfaces, and schemas |
| Guard | Declared policy decision based on current typed provider facts |
| Navgraph | Durable product locations plus exact operation/outcome transitions |
| Node | Product-facing location; not an agent-orchestration graph node |
| Opaque handle | Public scoped reference to a private product entity ID |
| Operation | Declared application-semantic read or write supervised by RouteDeck |
| Outcome | Typed handler result name that selects one declared transition/effect branch |
| Outcome-unknown | State where RouteDeck cannot prove whether a mutation or external write committed |
| Private form | Encrypted no-store channel for declared private fields outside public projection |
| Projection | Default-deny public view of canonical session state |
| Provider | Product implementation that loads current facts or entity allowlists for an operation |
| Request fingerprint | Canonical hash of a mutation's semantic input under its request ID |
| Request ID | Caller-owned durable replay identity for a mutation |
| Resume handle | Secret-bearing session-bound navigation credential |
| Review | Durable proposal that must be accepted/rejected and revalidated before execution |
| Route entry | Exact binding from route parameters to a supervised product operation |
| Session | One durable selected interaction context |
| Session selector | Host-owned authentication/authorization seam returning one internal session ID |
| Surface | Declared product component identity, public schema, lifecycle, and affordances |
| Transition | Exact source operation/outcome to target node mapping |

For normative field semantics, use the
[canonical reference](https://github.com/saastoagent/routedeck/blob/main/docs/route-deck-reference.md).
