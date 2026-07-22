# Medusa Reference Consumer

## Purpose

The standalone Medusa guest-buyer application proves RouteDeck portability
against a real local product API. It owns every commerce fact and side effect;
it consumes one framework-owned runtime, transport, and browser state path.

## Owner Files

- `examples/medusa-agent/backend/medusa_agent/features/`
- `examples/medusa-agent/backend/medusa_agent/medusa/client/`
- `examples/medusa-agent/backend/medusa_agent/{composition,bindings,session,runtime,agent,contact_identity}.py`
- `examples/medusa-agent/backend/main.py`
- `examples/medusa-agent/frontend/src/`
- `examples/medusa-agent/{medusa,infra,scripts,e2e}/`

## Product Feature Ownership

- Catalog owns real product/variant discovery and shareable product entry.
- Cart owns one real guest cart and line-item mutations.
- Checkout owns private contact/address, shipping, and payment initialization.
- Orders own reviewed placement, independent reread/reconciliation, and
  confirmation.
- The typed Store client owns Medusa endpoints, wire decoding, delivery
  evidence, and sanitized failures.
- Product agent code owns prompts, model roles, graph topology, and wording.
- Product React code owns surfaces, markdown rendering, navigation layout, and
  recovery copy.

## Boundary

Medusa selects `Feature` modules in `MEDUSA_APP`, binds product implementations,
and passes product callbacks/configuration to the SQLAlchemy runtime opener. It
does not construct generic runners, navigation, FastAPI dependencies, or the
LangGraph driver. The browser never calls `/store/*`.

The local host explicitly installs `GuestCookieSessionSelector` and supplies
the cookie, browser-origin, instance, review/resume TTL, and worker policy from
validated environment configuration. Multiple browser profiles are isolated;
tabs in one profile share that guest session. An authenticated product would
install its own `RouteDeckSessionSelector`; authentication and authorization do
not move into RouteDeck.

Medusa retains only greeting policy/copy around RouteDeck's reusable
assistant-turn coordinator. Its application root consumes
`RouteDeckBootstrapBoundary`; the recovery shell receives normalized state and
renders product wording/buttons without reading pending requests or calling
store recovery methods directly. Checkout and orders share the product-owned
`contact_identity.py` fingerprint. Backend JSON schemas and eight corresponding
frontend decoders execute the same checked-in parity vectors under
`contracts/surface-props-parity.json`. This parity gate covers those eight
decoders exactly; it is not a claim about undeclared or conditional surfaces.

## Evidence

Use focused backend/frontend tests for the feature in scope. The contact
identity and surface parity commands, plus protected real-commerce/browser
gates, are defined in `test_index/README.md`; this document does not itself
claim a current pass.
