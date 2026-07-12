# LangGraph Integration

## Purpose

This optional component connects a product-owned LangGraph application to the
RouteDeck interaction kernel. The product keeps its existing
`create_agent(...)` composition or raw `StateGraph` topology. RouteDeck never
accepts, compiles, synthesizes, or mutates that topology.

RouteDeck remains authoritative for durable interaction, session, navigation,
review, conversation, event, and public-projection state. Product handlers and
tools remain application-owned, but every product operation enters the same
`RouteDeckOperationRunner` used by HTTP and UI affordances.

## Owner Files

- `routedeck_langgraph/middleware.py`
- `routedeck_langgraph/tool_wrapper.py`
- `routedeck_langgraph/model_context.py`
- `routedeck_langgraph/conversation.py`
- `routedeck_langgraph/graph.py` (deprecated migration failure only)
- `routedeck_langgraph/__init__.py`

## Current Public Interfaces

- `RouteDeckMiddleware`
- `RouteDeckToolWrapper`
- `awrap_tool_call`
- `RouteDeckInvocationContext`
- `RouteDeckRunnerRuntime`
- `RouteDeckToolConfigurationError`
- `build_model_context(...)` and the typed model-context contracts
- durable conversation reconstruction helpers

`RouteDeckMiddleware` loads the current durable session before each model call,
reconstructs finalized conversation context, projects the default-deny public
model context, and filters the model's tools to operations legal at that exact
session version.

`RouteDeckToolWrapper` and `awrap_tool_call` translate structured tool calls
into supervised `OperationRequest` values. They delegate to the single
`RouteDeckOperationRunner`; the LangGraph continuation is not a second product
executor and is never called after the runner executes an operation.

## Invocation Contract

Each invocation supplies a `RouteDeckInvocationContext` with non-empty
`session_id` and `request_id_prefix`. The caller may also provide
`expected_session_version`, the claimed parent `turn`, and finalized
`review_turns`. The exported raw `awrap_tool_call` callback additionally reads
`routedeck_runtime` from that context; a callback bound through
`RouteDeckToolWrapper(runtime)` already owns the runtime.

The runtime must expose one `RouteDeckOperationRunner`. All model tools must be
the runner-owned schema tools returned by `RouteDeckToolWrapper.tools`. Direct
product handlers inside a `ToolNode` are rejected because they could bypass
guards, review, idempotency, durable commit, and projection.

## State And Checkpoint Ownership

A LangGraph checkpointer may retain product orchestration data needed by the
product graph. It is not authoritative for RouteDeck interaction state and may
not introduce a second execution, review, or commit path. RouteDeck state is
loaded from and committed through the configured RouteDeck session store.

## Retired Compatibility Seam

`build_route_deck_state_graph(...)` deliberately raises
`RouteDeckTopologyBuilderDeprecatedError`. Its import exists only to make an
old integration fail with a migration message; it is not an integration API.

`validate_langgraph_contract`, `assert_route_transition`, and
`matching_route_deck_edge` encode the retired manifest-handler/node parity
model. They are absent from `routedeck_langgraph.__all__` and current guidance.
Explicit lazy imports remain temporarily available for Corpus compatibility
until that consumer completes its separately approved migration.

Do not mirror RouteDeck nodes into LangGraph nodes. RouteDeck compiles product
features into interaction contracts; the product graph independently owns its
orchestration topology.

## Dependent Flows

- Product-owned `create_agent(...)` applications using RouteDeck middleware.
- Product-owned raw `StateGraph` applications using supervised `ToolNode`
  wrapping.
- UI, HTTP, and agent operations converging on one runner and durable session.

## Tests And Evidence

- `tests/test_public_api.py`
- `tests/test_langgraph_adapter.py`
- `examples/medusa-agent/backend/tests/contract/test_agent_middleware.py`
- `python -m pytest tests/test_public_api.py tests/test_langgraph_adapter.py examples/medusa-agent/backend/tests/contract/test_agent_middleware.py -q`

## Update Triggers

Update this doc and `architecture/code-map.md` when changing middleware model
context, invocation context, supervised tool wrapping, conversation
reconstruction, optional LangGraph dependencies, compatibility exports, or
graph/state ownership.

The integration must stay product-neutral. Product prompts, models, graph
topology, persistence for private orchestration data, and domain behavior
belong to the consuming application.
