# Deprecated Corpus-Only React Compatibility

This top-level `react/` tree is a deprecated compatibility package retained for
the active Corpus consumer. It is not the current RouteDeck React source tree,
must not gain new consumers, and must not be used as public-readiness or
publication evidence.

New applications use:

- `packages/core` / `@routedeck/core` for contracts, HTTP/SSE, store, routing,
  history, and private-form state.
- `packages/react` / `@routedeck/react` for providers, hooks, surfaces,
  navigation, review, status, private forms, and inspector primitives.
- `packages/testing` / private `@routedeck/testing` for test-only harnesses.

This directory temporarily shares the npm name `@routedeck/react` with the
current `packages/react` package. Keep the distinction explicit: this tree is
private and source-exported for Corpus compatibility; `packages/react` is the
authoritative built package.

## Removal Gate

Do not delete this directory until all of the following are true:

1. Corpus no longer installs or imports the top-level package.
2. Every still-required behavior has migrated to `packages/core` or
   `packages/react` without creating a second state or execution path.
3. Current package tests, typecheck, build, and focused Corpus compatibility
   proof pass against the migrated consumer.
4. The removal is explicitly approved as a separate change.

Until that gate is complete, changes here are compatibility maintenance only.
Do not publish this package, point new documentation at it, or add product
features to it.
