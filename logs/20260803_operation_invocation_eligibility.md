# Operation invocation eligibility implementation

Date: 2026-08-03

## Outcome

RouteDeck Operations now require an explicit non-empty set of allowed
invocation sources: agent, surface, route, and/or system. Node legality remains
separate from source eligibility.

- Compiler validation rejects SurfaceAffordance and SuggestedAction bindings
  that do not allow surface invocation and RouteEntry bindings that do not
  allow route invocation.
- Public projection retains node-legal Operations and their sorted allowed
  sources.
- LangGraph model context exposes only node-legal Operations that allow agent
  invocation as tools.
- The supervised runner blocks `operation_source_not_allowed` during source
  validation, before providers, guards, review, or product handlers.
- Python and generated TypeScript contracts and strict decoders carry the new
  public projection field.
- RouteDeck-owned test declarations and the Medusa reference declarations were
  migrated explicitly. The route resolver is route-only; other Medusa sources
  preserve their existing agent/surface/system behavior.

## Validation

- New focused source tests: 6 passed.
- Compiler/context/projection/supervision/navigation/LangGraph lane: 320 passed
  with the unrelated stale turn-lifecycle assertion excluded.
- State: 49 passed.
- FastAPI: 68 passed with one upstream deprecation warning.
- Persistence: 4 passed.
- Headless core: 88 passed; strict typecheck and build passed.
- Generated contracts: current.
- React: 22 passed; strict typecheck passed.
- Testing package: 15 passed.
- Medusa frontend: 72 passed.
- Focused updated Medusa agent-tool and route-entry assertions: 2 passed.
- Ruff: passed. Mypy reported four unrelated existing errors in LangGraph
  invocation tracing and Medusa runtime graph-factory typing; no mypy-pass
  claim is made.

The broader Medusa backend lane passed 49 tests and exposed one unrelated
scripted-chat replay expectation mismatch. The broad public/boundary lane
passed 51 tests and exposed the already-documented stale root `__all__`
expectation. The full Python aggregate did not complete cleanly in this
checkout, so no aggregate-pass claim is made.

## Browser E2E attempt

The protected local Medusa/Postgres/Redis services were healthy. The first live
startup exposed a stale Medusa adapter lambda that omitted the invocation-trace
argument required by the current graph-factory contract. The adapter was fixed,
its focused runtime tests passed (8), and focused mypy validation passed.

After that fix, the Agent API and frontend started. The current demo env file's
key entry was empty, so the approved existing agent-core RouteDeck backend key
was loaded into the stack process in memory, as prescribed by the prior live-E2E
runbook; no credential was printed or written into source. Readiness then
returned `200 {"status":"ready"}`.

The in-app browser loaded `http://127.0.0.1:5198/` as `Medusa Agent` with no
browser console warnings or errors. The live initial model response completed,
the `Browse products` surface action moved Welcome to Products, and a live user
message (`Show me the available products.`) produced an authoritative four-item
catalog response. This proves the live surface and agent invocation paths run
with the new eligibility contract.

Browser E2E initially exposed a stale example composition: the frontend registry
omitted 17 structural components declared by the compiled contract. The Medusa
consumer now registers those frame/status/error/diagnostic contracts through an
explicit guarded nonvisual structural adapter. The adapter rejects unsupported
slots and projected props rather than hiding a product-surface mismatch.

After the migration, the registry error disappeared and `Browse products`
rendered the real four-product catalog grid. The live model/tool response,
surface navigation, browser DOM, screenshot, and console checks passed. Medusa
frontend validation is now 73 tests across 18 files; strict typecheck and build
also pass. No mock or scripted-model fallback was used.

No live model, deployment, publication, commit, or push was part of this
implementation.

## Ownership

- Core contract/compiler/projection/runner: compiled application and
  interaction runtime.
- Model tool filtering: optional LangGraph adapter.
- Generated decoder and schema: headless TypeScript runtime and packaging.
- Explicit Medusa source declarations: standalone Medusa reference consumer.
- Canonical/reference/coverage/log updates: architecture and context governance.
