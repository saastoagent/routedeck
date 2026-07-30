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
  `assistant_initiated` streams plus ignored event tags.
- `RouteDeckLangGraphDriverFactory`: calls the product graph factory once after
  `RouteDeckRuntimeServices` exists and constructs the generic driver.
- `RouteDeckLangGraphAgentDriver`: translates `astream_events(...)` into typed
  text/reset/review/completion events and closes the async stream.
- `UserMessageTrigger` and `AssistantInitiatedTrigger` through the core driver
  port.
- `RouteDeckMiddleware`, `RouteDeckToolWrapper`,
  `RouteDeckInvocationContext`, and `build_model_context(...)`.
- strict durable user/assistant conversation extraction helpers.

User-message extraction requires exactly one matching `HumanMessage` marker
and may supervise serial tools/review. Assistant initiation sends no
`HumanMessage`, permits exactly one streamed non-tool assistant result, and
rejects tool calls or review output.

## Ownership Rules

- RouteDeck's navgraph and the product model graph remain separate.
- Middleware exposes only default-deny current context and legal operations.
- Middleware selects the product-authored prompt from the feature that owns the
  current node and composes it before resolved policies and untrusted JSON
  context; RouteDeck does not author product prompt content.
- Every structured product tool call reaches the runtime's one operation
  runner; the adapter never calls a product handler directly.
- A product graph factory returns an explicit graph set or `None`; a missing or
  failing graph/model is not replaced by another provider or canned response.
- Product production modules do not construct `RouteDeckLangGraphAgentDriver`
  or call `astream_events(...)` themselves.

## Evidence

```powershell
python -m pytest tests/test_langgraph_agent_driver.py tests/test_langgraph_model_context.py tests/test_langgraph_policy_prompt.py examples/medusa-agent/backend/tests/contract/test_agent_middleware.py -q
```

Update this document when trigger rules, feature-prompt selection,
graph-factory ownership, model-context filtering, event translation, stream
cleanup, or tool supervision changes.
