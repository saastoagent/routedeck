# Context Checkpoint - 22-07-2026 RouteDeck Wiki Mermaid

Project: RouteDeck
Status: local wiki reader and diagram rendering complete; registry and GitHub
Wiki publication pending
Runtime boundary: local Windows; the Vite reader is running at
`http://127.0.0.1:5176/?page=Architecture`; no framework or Medusa service
started

## Read Next

1. `critical_prompt.md`
2. `context.md`
3. `wiki-site/src/MermaidDiagram.tsx`
4. `wiki-site/src/MarkdownArticle.tsx`
5. `wiki-site/README.md`
6. `architecture/components/examples-and-adoption.md`

## Completed

- Added exact `mermaid` 11.16.0 as the approved private reader dependency.
- Lazy-load and initialize it once with `securityLevel: "strict"` and
  `startOnLoad: false`.
- Render checked-in Mermaid blocks as responsive SVGs while retaining a source
  disclosure below every diagram.
- Fail visibly with the original source when Mermaid rejects a diagram.
- Added focused success/failure tests and recorded dependency ownership,
  license, configuration, and verification.

## Current Proof

- `pnpm --filter @routedeck/wiki-site test`: 5 tests passed.
- `pnpm --filter @routedeck/wiki-site typecheck`: passed.
- `pnpm --filter @routedeck/wiki-site build`: passed.
- `pnpm audit --prod --audit-level high`: no known vulnerabilities found.
- `python scripts/check_doc_coverage.py`: 634/634 live files mapped.
- `python scripts/check_context_architecture.py`: 63 active Markdown files
  passed.
- Live browser: Architecture rendered one flowchart; How RouteDeck Works
  rendered flowchart and sequence SVGs; Operations and Supervision rendered
  flowchart and state SVGs; no render alerts were present.
- Source disclosure opened and exposed the original `flowchart TB` source.
- Desktop 1536x1024 and mobile 390x844 screenshots were inspected; the mobile
  document had zero horizontal overflow.

## Remaining

- The reader is local-only and has not been deployed.
- Publishing `wiki/` to the separate GitHub Wiki repository remains a distinct,
  explicitly authorized git operation.
- Registry package publication and coverage hardening are unchanged.
- The production build contains a deferred Mermaid chunk; it is loaded only on
  articles containing Mermaid source. Vite reports that 662.68 kB minified
  chunk against its 500 kB advisory threshold.
