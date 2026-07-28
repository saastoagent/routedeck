# Context Checkpoint - 22-07-2026 RouteDeck Wiki Reader

Project: RouteDeck
Status: local wiki reader complete; registry and GitHub Wiki publication pending
Runtime boundary: local Windows; the Vite reader is running at
`http://127.0.0.1:5176/?page=Home`; no framework or Medusa service started

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
- `python scripts/check_doc_coverage.py`: 633/633 live files mapped.
- `python scripts/check_context_architecture.py`: passed.
- Live browser verification: desktop and 390 px mobile layouts rendered;
  navigation, search, URL state, and the mobile drawer worked; no console
  warnings or errors were recorded.
- `python -m pytest tests/test_doc_coverage_checker.py -q`: 1 passed; local
  `.worktrees` trees are pruned before traversal.

## Remaining

- The reader is local-only and has not been deployed.
- Mermaid blocks are currently presented as labelled source pending approval
  of a diagram-renderer dependency.
- Publishing `wiki/` to the separate GitHub Wiki repository remains a distinct,
  explicitly authorized git operation.
- Registry package publication and coverage hardening are unchanged.
