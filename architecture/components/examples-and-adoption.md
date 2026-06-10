# Examples And Adoption

## Purpose

This component owns RouteDeck's adoption examples. The active visible example
is `examples/medusa-agent`, which proves RouteDeck by staying a product-owned
agent while RouteDeck behavior is introduced underneath it in small slices.
Generic product-neutral examples are deferred and must not be used as a
substitute for a requested Medusa Agent slice.

Product-specific examples must not move Medusa behavior into RouteDeck core,
React, LangGraph adapter packages, or product-specific
`/api/routedeck/<domain>/*` routes.

## Owner Files

- `examples/medusa-agent/*`
- `docs/minimal-example.md`
- `docs/using-routedeck.md`

## Public Interfaces

- Medusa Agent product reference example.
- Deferred product-neutral example policy in `docs/minimal-example.md`.
- Product-specific Medusa example contract in
  `docs/medusa-agent-reference-app.md`.
- Example README files and adoption commands.

## Dependent Flows

- Product teams learning how RouteDeck sits underneath an agent-first product.
- Clean-install smoke checks.
- Public alpha readiness.
- Regression checks that RouteDeck remains product-neutral while examples stay
  product-owned.

## Tests And Evidence

- `python -m pytest tests -q`
- `cd react && npm test`
- Medusa example README and tests for product/framework boundary wording.

## Update Triggers

Update this doc and `architecture/code-map.md` when changing:

- example route shape
- example manifest/runtime projection shape
- example frontend consumption pattern
- adoption instructions
- public docs that describe examples

Deferred generic examples must remain product-neutral and must not depend on
private local credentials, SaaStoAgent database models, or Medusa-specific
behavior. Product-specific examples may demonstrate a domain only inside their
own example folder, with product-owned routes for domain behavior and
RouteDeck-derived state. Do not create a standalone RouteDeck dashboard to
claim progress on a Medusa Agent visible slice.
