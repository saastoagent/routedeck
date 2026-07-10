# Examples And Adoption

## Purpose

This component owns RouteDeck's adoption examples. Medusa remains a
product-owned reference integration, but RouteDeck framework readiness now also
requires two self-contained examples independent of Corpus and Medusa.

1. **Full Flow example:** an ordinary developer declares an application and
   RouteDeck compiles/runs the LangGraph backend, typed event/SSE path,
   projection, and React surfaces.
2. **Core Integration example:** an advanced developer keeps an existing/custom
   agent execution graph and attaches it to RouteDeck state and interaction
   management through the executor adapter.

Product-specific examples must not move Medusa behavior into RouteDeck core,
React, LangGraph adapter packages, or product-specific
`/api/routedeck/<domain>/*` routes.

## Owner Files

- `examples/medusa-agent/*`
- `examples/full-flow-change-planner/*` (planned)
- `examples/core-integration-document-review/*` (planned)
- `docs/minimal-example.md`
- `docs/using-routedeck.md`

## Public Interfaces

- Medusa Agent product reference example.
- Full Flow and Core Integration runnable adoption contracts.
- Product-specific Medusa example contract in
  `docs/medusa-agent-reference-app.md`.
- Example README files and adoption commands.

## Dependent Flows

- Product teams learning how RouteDeck sits underneath an agent-first product.
- Clean-install smoke checks.
- Conformance proof that both adoption modes share operations, guards, events,
  projections, surfaces, and store behavior.
- Public alpha readiness.
- Regression checks that RouteDeck remains product-neutral while examples stay
  product-owned.

## Tests And Evidence

- `python -m pytest tests -q`
- `cd react && npm test`
- Medusa example README and tests for product/framework boundary wording.
- Planned per-example backend pytest, frontend test/build, clean-install,
  compose, browser, and shared two-mode conformance checks.

## Update Triggers

Update this doc and `architecture/code-map.md` when changing:

- example route shape
- example manifest/runtime projection shape
- example frontend consumption pattern
- adoption instructions
- public docs that describe examples

The standalone examples must remain product-neutral and must not depend on
private local credentials, SaaStoAgent/Corpus database models, or Medusa
behavior. They must use real in-process domain behavior, fail loudly when a
required real integration is unavailable, keep fixtures inside tests, and ship
with README, backend tests, frontend tests, and smoke commands. Product-specific
examples may demonstrate a domain only inside their own example folder, with
product-owned routes for domain behavior and RouteDeck-derived state.
