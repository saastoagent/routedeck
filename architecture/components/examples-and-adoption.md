# Examples And Adoption

## Purpose

This component owns runnable adoption evidence. The standalone Medusa buyer
agent is the current product-owned reference consumer; generic framework docs
explain the same product-neutral contracts without moving Medusa behavior into
RouteDeck.

A new application follows one current path:

1. Declare product-owned `Feature` modules whose nodes own their outgoing
   transitions, then select them in an `Application`.
2. Call `compile_app(...)`, then `bind_app(...)` with real product providers,
   guards, context providers, and operation handlers.
3. Pass product callbacks and explicit persistence configuration to a RouteDeck
   runtime opener; do not construct generic runners or FastAPI dependencies in
   the product.
4. If the product uses LangGraph, keep its `create_agent(...)` or raw
   `StateGraph` topology and attach `RouteDeckMiddleware` plus supervised tool
   wrapping. RouteDeck does not compile product graph topology.
5. Consume the public contract through `@routedeck/core` and
   `@routedeck/react`; use `@routedeck/testing` only in tests.

## Owner Files

- `examples/medusa-agent/*`
- `examples/hello-world/*`
- `wiki/*`
- `docs/minimal-example.md`
- `docs/using-routedeck.md`
- `docs/medusa-agent-reference-app.md`
- `README.md`, `ROADMAP.md`, and the public participation documents

## Public Interfaces

- Feature-composed Python authoring and binding.
- Shared runner, durable session, projection, event, and transport contracts.
- Optional non-topology-owning LangGraph middleware/tool integration.
- Headless and React packages from `packages/core` and `packages/react`.
- Medusa as a product-owned reference, not a framework dependency or default.

## Dependent Flows

- Developers learning the framework/product ownership boundary.
- Clean-install and package-import checks.
- Conformance proof that HTTP, UI, and agent operations share one runner.
- Regression checks that framework packages stay product-neutral while the
  example owns prompts, domain APIs, models, handlers, and product surfaces.

## Tests And Evidence

- `python -m pytest tests/examples/test_hello_world_example.py -q`
- `python -m pytest tests/app tests/supervision tests/test_langgraph_agent_driver.py -q`
- `python -m pytest examples/medusa-agent/backend/tests -q` with real-Medusa
  lanes run only against the configured protected local stack.
- `pnpm --filter @routedeck/medusa-agent test`
- `pnpm --filter @routedeck/medusa-agent typecheck`
- `pnpm --filter @routedeck/medusa-agent build`
- protected local browser and release harnesses listed in `test_index/README.md`
- built-artifact inventory and isolated-consumer checks listed in
  `docs/releasing.md`

## Update Triggers

Update this doc and `architecture/code-map.md` when feature composition,
binding, runner ownership, optional LangGraph integration, example routes,
frontend package consumption, wiki structure, Hello World behavior, or adoption
instructions change.

Examples use real in-process behavior or an explicitly configured real
integration and fail loudly when required data or credentials are unavailable.
Fixtures and scripted models remain isolated under tests; no example product
path silently substitutes canned data, handlers, or responses.
