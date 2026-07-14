---
name: routedeck-langgraph-integration
description: Use when adding RouteDeck durable interaction state and supervised operations to a product-owned create_agent or raw StateGraph application.
---

# RouteDeck LangGraph Integration

Keep the product's LangGraph topology. RouteDeck integrates at model and tool
boundaries; it does not generate, mirror, or mutate graph nodes and edges.

## `create_agent(...)`

Use runner-owned schema tools and the middleware together:

```python
from langchain.agents import create_agent
from routedeck_langgraph import (
    RouteDeckInvocationContext,
    RouteDeckMiddleware,
    RouteDeckToolWrapper,
)

wrapper = RouteDeckToolWrapper(runtime)
agent = create_agent(
    model=model,
    tools=wrapper.tools,
    middleware=(RouteDeckMiddleware(runtime),),
    context_schema=RouteDeckInvocationContext,
)

result = await agent.ainvoke(
    {"messages": messages},
    context={
        "session_id": session_id,
        "request_id_prefix": request_id,
    },
)
```

`runtime` must expose one `RouteDeckOperationRunner` as `.runner`, or be that
runner. `RouteDeckMiddleware` loads the durable session, reconstructs finalized
conversation turns, supplies the default-deny public model context, and limits
the model to operations legal in that session.

## Raw `StateGraph` / `ToolNode`

The bound wrapper is the simplest raw-graph shape:

```python
from langgraph.graph import MessagesState, StateGraph
from routedeck_langgraph import RouteDeckInvocationContext, RouteDeckToolWrapper

wrapper = RouteDeckToolWrapper(runtime)
graph = StateGraph(MessagesState, context_schema=RouteDeckInvocationContext)
graph.add_node("tools", wrapper.tool_node())
# Add the product-owned model node, routing, entry point, and edges here.
compiled_graph = graph.compile(checkpointer=product_checkpointer)
```

When graph construction cannot close over the runtime, use the exported raw
callback and pass the runtime in invocation context:

```python
from langgraph.prebuilt import ToolNode
from routedeck_langgraph import awrap_tool_call

graph.add_node(
    "tools",
    ToolNode(wrapper.tools, awrap_tool_call=awrap_tool_call),
)

context = {
    "session_id": session_id,
    "request_id_prefix": request_id,
    "routedeck_runtime": runtime,
}
```

The product still owns all conditional edges and orchestration state. A
LangGraph checkpointer may persist that private orchestration data, but it is
not the authority for RouteDeck session, navigation, review, conversation, or
projection state.

## Invocation And Execution Rules

- `session_id` and `request_id_prefix` are required non-empty strings.
- `expected_session_version`, `turn`, and `review_turns` are optional typed
  context values used for concurrency and parent-turn lifecycle.
- Use only `RouteDeckToolWrapper.tools` in the supervised `ToolNode`.
- Every UI, HTTP, and agent operation delegates to the same
  `RouteDeckOperationRunner`.
- Do not call product tool handlers directly from LangGraph. The continuation
  passed to the wrapper is not a fallback executor and is deliberately not
  invoked after the RouteDeck runner executes.
- Fail on missing context or an unowned tool; never substitute a second state
  source or execution path.

## Graph Boundary

RouteDeck exports no topology builder or handler/node parity helper. Do not
mirror RouteDeck nodes into LangGraph nodes.

## Focused Verification

```powershell
python -m pytest tests/test_public_api.py tests/test_langgraph_model_context.py examples/medusa-agent/backend/tests/contract/test_agent_middleware.py -q
```
