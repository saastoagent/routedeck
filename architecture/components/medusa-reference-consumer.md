# Medusa Reference Consumer

## Purpose

The standalone Medusa guest-buyer application proves RouteDeck portability
against a real local product API. It owns every commerce fact and side effect;
it consumes one framework-owned runtime, transport, and browser state path.

## Owner Files

- `examples/medusa-agent/backend/medusa_agent/features/`
- `examples/medusa-agent/backend/medusa_agent/medusa/client/`
- `examples/medusa-agent/backend/medusa_agent/{composition,bindings,session,runtime,agent}.py`
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

The current guest adapter selects one session with an HTTP-only cookie. Multiple
browser profiles are isolated; tabs in one profile share that guest session.
Authenticated user/session authorization remains consumer-owned and is not yet
a framework FastAPI resolver.

## Evidence

Use focused backend/frontend tests for the feature in scope. Real commerce and
browser gates require the protected local stack and are defined only in
`test_index/README.md`; this document does not claim that they currently pass.
