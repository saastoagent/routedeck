# Testing and Diagnostics

RouteDeck tests are organized by the claim they support. A passing unit test is
not a substitute for proving the real product path.

## Proof layers

| Layer | What it can prove |
| --- | --- |
| Compiler/binding tests | Invalid declarations and ownership fail before runtime |
| State/supervision tests | Invariants, idempotency, review, effects, and recovery semantics |
| Persistence tests | Transactions, fencing, restart, retention, and encrypted blobs |
| FastAPI tests | HTTP contract, selector boundary, status mapping, SSE, and forms |
| TypeScript package tests | Strict decode, bootstrap, request retention, event convergence, history |
| React tests | Product-neutral primitive lifecycle and presentation behavior |
| Medusa contract/integration tests | Product/framework boundary and real Store API behavior |
| Playwright/live-model checks | Actual rendered buyer flow and integrations |

Use the repository
[test index](https://github.com/saastoagent/routedeck/blob/main/test_index/README.md)
for current commands and the exact claims each command can support.

## Hello World proof

From the repository root:

```powershell
python -m pytest tests/examples/test_hello_world_example.py -q
```

This proves the checked-in tutorial compiles and binds against the current
checkout. It does not prove persistence, HTTP, browser, or live integrations.

## Compiler-derived test paths

Compilation derives executable paths for transitions, safety, deep-link,
review, and recovery branches. These make graph coverage inspectable without
turning generated output into source authority.

## Read-only inspection

`GET /api/routedeck/inspect` exposes public topology and limited diagnostics.
The React Navgraph renders the complete compiled transition contract and
highlights current and reachable nodes.

Inspection is deliberately non-authoritative:

- selecting a node does not navigate;
- diagnostics do not become product actions;
- private IDs and private-form values are absent;
- diagnostic data does not enter normal model context.

## Useful debugging order

1. Confirm which runtime, database, and host are actually in use.
2. Inspect the selected session and current versions.
3. Check the request ID/fingerprint and whether a result was already recorded.
4. Check provider facts, guard disposition, and opaque-handle scope.
5. Check the declared operation/outcome transition and effect validation.
6. Check persisted event cursor before live SSE delivery.
7. Check browser decode/version convergence before product presentation.
8. For external writes, verify the product source of truth independently.

## Evidence discipline

Report the exact command, runtime location, test count, relevant artifact, and
what remains unverified. A prior run, screenshot, or generated report does not
prove a later checkout unless its source and environment are still the same.
