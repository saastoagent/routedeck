# Context Checkpoint - 22-07-2026 RouteDeck Wiki Reader

Project: RouteDeck
Status: local wiki reader complete; registry and GitHub Wiki publication pending
Runtime boundary: local Windows; no framework or Medusa service started

## Read Next

1. `critical_prompt.md`
2. `context.md`
3. `wiki/Home.md`
4. `wiki-site/src/App.tsx`
5. `architecture/components/examples-and-adoption.md`
6. `test_index/README.md`

## Completed

- Added a private Vite/React workspace that reads the checked-in `wiki/`
  Markdown without creating a second content source.
- Added local search, navigation, responsive layout, and Markdown rendering.
- Added root commands for local development, focused tests, and production
  build.
- Mapped the reader into developer-learning ownership and validation docs.

## Current Proof

- `pnpm wiki:test`: 4 tests passed.
- `pnpm --filter @routedeck/wiki-site typecheck`: passed.
- `pnpm wiki:build`: passed.
- `python scripts/check_doc_coverage.py`: 631/631 live files mapped.
- `python scripts/check_context_architecture.py`: passed.

## Remaining

- The reader is local-only and has not been deployed.
- Publishing `wiki/` to the separate GitHub Wiki repository remains a distinct,
  explicitly authorized git operation.
- Registry package publication and coverage hardening are unchanged.
