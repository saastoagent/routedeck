# LangGraph Integration

## Purpose

This optional adapter connects a product-owned LangGraph agent to RouteDeck.
The product keeps its `create_agent(...)` or `StateGraph` topology; RouteDeck
does not accept, synthesize, compile, or mutate that graph.

RouteDeck remains authoritative for interaction session, navigation, review,
conversation, event, and public-projection state. Every structured product tool
call enters the same `RouteDeckOperationRunner` used by UI affordances and HTTP.

## Owner Files

- `routedeck_langgraph/middleware.py`
- `routedeck_langgraph/tool_wrapper.py`
- `routedeck_langgraph/model_context.py`
- `routedeck_langgraph/conversation.py`
- `routedeck_langgraph/__init__.py`

## Public Interfaces

- `RouteDeckMiddleware`
- `RouteDeckToolWrapper` and `awrap_tool_call`
- `RouteDeckInvocationContext` and `RouteDeckRunnerRuntime`
- `RouteDeckToolConfigurationError`
- `build_model_context(...)` and typed model-context contracts
- durable conversation reconstruction helpers

Middleware loads the current durable session before each model call,
reconstructs finalized conversation, injects default-deny public context and
active policies, and exposes only operations legal for that session version.
The tool wrapper converts structured calls to `OperationRequest` and delegates
to the one runner; it never invokes product handlers directly.

## Ownership Rules

- Invocation requires non-empty `session_id` and `request_id_prefix`.
- A LangGraph checkpointer may retain product orchestration data but is not an
  interaction-state or commit authority.
- RouteDeck nodes are not mirrored into LangGraph nodes. The compiled navgraph
  and the product orchestration graph solve different problems.
- Product prompts, model roles, topology, and business behavior remain in the
  consuming application.

## Evidence

- `tests/test_public_api.py`
- `tests/test_langgraph_model_context.py`
- `examples/medusa-agent/backend/tests/contract/test_agent_middleware.py`
- `examples/medusa-agent/backend/tests/integration/test_agent_chat_flow.py`
