# Examples And Adoption

## Purpose

This component owns RouteDeck's product-neutral adoption examples. Minimal
examples must teach integration without importing SaaStoAgent product behavior.
Future product-specific examples, such as `examples/medusa-agent`, may expose a
separate generic RouteDeck API plane next to their product APIs. They must not
move Medusa behavior into RouteDeck core, React, LangGraph adapter packages, or
product-specific `/api/routedeck/<domain>/*` routes.

## Owner Files

- `examples/minimal-langgraph-adapter/*`
- `examples/minimal-fastapi-react/*`
- `docs/minimal-example.md`
- `docs/using-routedeck.md`

## Public Interfaces

- Minimal backend-only LangGraph adapter example.
- Minimal FastAPI/React full-contract example.
- Future product-specific Medusa example contract, currently documented only in
  `docs/medusa-agent-reference-app.md`.
- Example README files and adoption commands.

## Dependent Flows

- New product teams learning RouteDeck.
- Clean-install smoke checks.
- Public alpha readiness.
- Regression checks that RouteDeck remains reusable outside SaaStoAgent.

## Tests And Evidence

- `python -m pytest tests -q`
- `cd react && npm test`
- Example README review for product-neutral wording.

## Update Triggers

Update this doc and `architecture/code-map.md` when changing:

- example route shape
- example manifest/runtime projection shape
- example frontend consumption pattern
- adoption instructions
- public docs that describe examples

Minimal examples must remain product-neutral and must not depend on private
local credentials, SaaStoAgent database models, or Medusa-specific behavior.
Product-specific examples may demonstrate a domain only inside their own example
folder, with product routes for domain behavior and generic RouteDeck routes for
framework state/projection/dispatch/inspect.
