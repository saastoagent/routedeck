# LangGraph Integration

Authority: ADR-006 for runtime ownership; ADR-005 remains active where ADR-006
does not supersede it.

## Purpose

This optional framework adapter connects product-supplied LangGraph event
streams to RouteDeck's typed conversation and supervised-operation lifecycle.
The product keeps its graph topology, prompts, models, policy, and wording;
RouteDeck owns the reusable driver and never synthesizes a product graph.

## Owner Files

- `routedeck_langgraph/agent_driver.py`
- `routedeck_langgraph/conversation.py`
- `routedeck_langgraph/middleware.py`
- `routedeck_langgraph/model_context.py`
- `routedeck_langgraph/prompt.py`
- `routedeck_langgraph/tool_wrapper.py`
- `routedeck_langgraph/__init__.py`

## Public Interfaces

- `RouteDeckLangGraphGraphs`: explicit `user_message` and
  `assistant_initiated` streams plus ignored event tags and an optional,
  product-declared inspection system prompt.
- `RouteDeckLangGraphDriverFactory`: calls the product graph factory once after
  `RouteDeckRuntimeServices` exists and constructs the generic driver.
- `RouteDeckLangGraphAgentDriver`: translates `astream_events(...)` into typed
  text/reset/review/completion events and closes the async stream.
- Every raw LangGraph `on_chat_model_start` event emits one standard structured
  `routedeck_langgraph_model_started` info log containing only the public
  RouteDeck `request_id` and LangChain `run_id`. The formatted message includes
  those same fields and uses the standard `uvicorn.error.routedeck.langgraph`
  hierarchy so default local/Uvicorn logging can count actual model starts.
  Prompts, event payloads, tokens, credentials, user/product data, and internal
  session identifiers are never logged by this boundary.
- `UserMessageTrigger` and `AssistantInitiatedTrigger` through the core driver
  port.
- `RouteDeckMiddleware`, `RouteDeckToolWrapper`,
  `RouteDeckInvocationContext`, and `build_model_context(...)`.
- `RouteDeckLangGraphAgentDriver.inspect_agent_context(...)` uses the same
  model context, tool-name projection, policy rendering, and product base
  prompt as middleware. It returns `None` when the product did not explicitly
  opt into prompt inspection; it never guesses or extracts a prompt from an
  opaque graph.
- strict durable user/assistant conversation extraction helpers.

User-message extraction requires exactly one matching `HumanMessage` marker
and may supervise serial tools/review. Assistant initiation sends no
`HumanMessage`, permits exactly one streamed non-tool assistant result, and
rejects tool calls or review output. Both trigger kinds receive a typed
`RouteDeckInvocationContext` containing the selected session, request prefix,
and durable turn lease so middleware can load scoped state. Assistant
initiation supplies `review_turns=()` and still starts with an empty message
list; context availability never creates a synthetic user turn.

## Ownership Rules

- RouteDeck's navgraph and the product model graph remain separate.
- Middleware exposes only default-deny current context and legal operations.
- Every structured product tool call reaches the runtime's one operation
  runner; the adapter never calls a product handler directly.
- A product graph factory returns an explicit graph set or `None`; a missing or
  failing graph/model is not replaced by another provider or canned response.
- Product production modules do not construct `RouteDeckLangGraphAgentDriver`
  or call `astream_events(...)` themselves.

## Evidence

```powershell
python -m pytest tests/test_langgraph_agent_driver.py tests/test_langgraph_model_context.py tests/test_langgraph_policy_prompt.py examples/medusa-agent/backend/tests/integration/test_entry_conversation.py -q
```

Update this document when trigger rules, graph-factory ownership, model-context
filtering, model-invocation observability, event translation, stream cleanup, or
tool supervision changes.
