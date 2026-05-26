# Examples And Adoption

## Purpose

This component owns RouteDeck's product-neutral adoption examples. Examples
must teach integration without importing SaaStoAgent product behavior.

## Owner Files

- `examples/minimal-langgraph-adapter/*`
- `examples/minimal-fastapi-react/*`
- `docs/minimal-example.md`
- `docs/using-routedeck.md`

## Public Interfaces

- Minimal backend-only LangGraph adapter example.
- Minimal FastAPI/React full-contract example.
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

Examples must remain product-neutral and must not depend on private local
credentials, SaaStoAgent database models, or Medusa-specific behavior.
