# Contributing to RouteDeck

RouteDeck is an early alpha. Contributions that improve the application-state
and interaction-governance runtime, adapters, documentation, or proof quality
are welcome. Product-specific features belong in consuming applications such
as the Medusa reference app, not in the framework.

## Before You Start

- Search existing issues and the public [roadmap](ROADMAP.md).
- Open an issue before a large API, dependency, architecture, or scope change.
- Treat accepted ADRs, the RouteDeck reference, and the feature-coverage matrix
  as implementation authority; the roadmap is directional.
- Never include credentials, user data, generated demo state, release bundles,
  or private service output.

## Local Setup

RouteDeck's checked-in toolchain targets Python 3.11+, Node 22.13.0+, and pnpm
11.7.0. On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[fastapi,langgraph,persistence,testing,dev]"
pnpm install --frozen-lockfile
```

Run the non-destructive checks relevant to your change:

```powershell
python -m pytest tests -q
python -m ruff check routedeck_core routedeck_fastapi routedeck_langgraph routedeck_sqlalchemy routedeck_testing tests
python scripts/check_boundaries.py --json "$env:TEMP\routedeck-boundary.json"
python scripts/check_doc_coverage.py
pnpm test
pnpm typecheck
pnpm build
```

The real Medusa and browser release paths have additional prerequisites and
must not be replaced with fixtures or silent fallbacks. See
[`docs/releasing.md`](docs/releasing.md).

## Pull Requests

Keep changes focused. Describe the source of truth, behavior changed, proof
run, and anything not verified. Add focused tests for contracts, invariants,
regressions, and failure semantics. Update only the documentation owners for
the changed subsystem.

By contributing, you agree that your contribution is licensed under the MIT
License and to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
