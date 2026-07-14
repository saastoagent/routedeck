# RouteDeck Standalone Extraction Report

Date: 2026-07-15 (Asia/Calcutta)

## Boundary

- Standalone repository: `D:\Dev\AI Projects\routedeck`
- Extracted source subtree: `agent-lab-powered-projects/routedeck`
- Branch: `main`
- Remotes: none
- GitHub push: not performed
- Original `agent-core` checkout: read-only throughout the extraction

The Medusa buyer agent remains the reference application under
`examples/medusa-agent`. Historical documents that intentionally describe the
old monorepo location are catalogued in `legacy-path-references.md`; current
instructions use standalone-relative paths.

## Preservation and history

- Preserved snapshot: 2,034 non-dependency files, 122,209,176 bytes
- Source working-state snapshot commit: `0a389f071ef66a7bbf5c2c4131b1f8cb6c192bf4`
- Standalone-boundary commit: `334b7f25bc769a22f1569ab7a1034453a2851a50`
- Relevant filtered source commits retained: 43 of 43
- Source-to-standalone commit map: `source-commit-map.tsv`
- Ignored source artifacts preserved: 1,415 non-dependency files
- Volatile SQLite databases: raw copies retained under the ignored
  `codex_chats_and_memories` archive; the active copy was created with SQLite's
  online backup API and passed integrity checking

`codex_chats_and_memories` is intentionally ignored by Git. Its manifest has
431 items, including 268 raw Codex sessions, totalling 3,325,968,250 bytes; a
fresh hash verification reported no missing or extra files.

## Recreated environments

- Python 3.11.9 virtual environment: `.venv`
- Python install: editable `.[fastapi,langgraph,persistence,testing,dev]`
- Medusa backend: editable install into the same environment
- Node.js 24.3.0
- pnpm 11.7.0
- Workspace dependencies: `pnpm install --frozen-lockfile` (170 packages)

Neither `.venv` nor `node_modules` was copied from the source tree. Both are
ignored in this repository.

## Verification

The following verification was run from this standalone repository:

- Python suite: 450 passed
- TypeScript unit suites: 71 passed (core 16, React 5, testing 12, Medusa
  frontend 38)
- TypeScript typechecks: all workspace packages passed, including E2E
- Workspace builds: all passed; the Medusa frontend built 261 modules
- Medusa backend focused suite: 46 passed
- Real isolated Medusa integration suite: 4 passed
- RouteDeck boundary guard: passed with zero violations
- Ignore-parity audit: all 1,415 source-ignored non-dependency files remain
  ignored; private probes were ignored and `.env.example` remained trackable

Small verification-only updates align stale test doubles and fixtures with the
current atomic turn/session and projection contracts. The real-Medusa tests now
accept an explicitly declared expected base URL, while retaining port 9100 as
their default.

## Local runtime smoke

Runtime location: local Windows machine.

Isolated Medusa was launched with Compose project
`routedeck-medusa-extracted` and the control-file port override. It uses fresh
Postgres and Redis volumes and generated local credentials:

```powershell
docker compose --project-name routedeck-medusa-extracted `
  --file .\examples\medusa-agent\infra\docker-compose.yml `
  --file "D:\Dev\AI Projects\agent-core-repo-extraction-control\work\routedeck-isolated-compose.override.yaml" `
  up --detach --build
```

The API and frontend commands were:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8099

$env:VITE_AGENT_API_PROXY_TARGET = 'http://127.0.0.1:8099'
C:\nvm4w\nodejs\pnpm.cmd --filter @routedeck/medusa-agent dev -- --port 5199
```

Smoke-test URLs:

- Medusa health: `http://127.0.0.1:9110/health` - HTTP 200
- RouteDeck API health: `http://127.0.0.1:8099/api/medusa-agent/health` - HTTP 200
- RouteDeck API readiness: `http://127.0.0.1:8099/api/medusa-agent/ready` - HTTP 503,
  `{"status":"not_ready"}`
- Frontend: `http://127.0.0.1:5199/` - HTTP 200
- Frontend proxy health: `http://127.0.0.1:5199/api/medusa-agent/health` - HTTP 200

A real HTTP flow against the isolated Medusa instance completed
`catalog.list`, `catalog.open_product`, `catalog.select_variant`,
`cart.add_item`, and `cart.open`; the final RouteDeck session was version 7 at
`cart.summary` with one active entity and projected cart operations.

The environment has no `OPENAI_API_KEY`, so live model conversation was not
claimed or replaced with a mock, cached response, or alternate provider. This
is the only remaining external readiness dependency for that path.
