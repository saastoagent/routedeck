# Packaging And Public Readiness

## Purpose

This component owns RouteDeck package metadata, canonical public imports,
release posture, and readiness evidence. The current source packages are the
Python framework modules plus the `packages/core`, `packages/react`, and
`packages/testing` workspace packages.

## Owner Files

- `pyproject.toml`
- `package.json`
- `pnpm-workspace.yaml`
- `packages/core/package.json`
- `packages/react/package.json`
- `packages/testing/package.json`
- `packages/*/src/index.ts`
- `README.md`
- `docs/packaging-roadmap.md`
- `react/README.md` (legacy Corpus-only quarantine notice)

## Current Public Interfaces

- Python distribution `routedeck-core`, including the dependency-light core
  and optional `langgraph`, `fastapi`, `sqlite`, and `testing` extras.
- Root Python authoring surface: `ApplicationSpec`, `FeatureSpec`,
  `CompiledRouteDeckApp`, `compile_app(...)`, and `bind_app(...)`.
- Python runner/session contracts such as `RouteDeckOperationRunner`,
  `RouteDeckSession`, and `RouteDeckSessionStore`.
- Headless npm package `@routedeck/core` from `packages/core`.
- React npm package `@routedeck/react` from `packages/react`.
- Private test-support package `@routedeck/testing` from `packages/testing`.

Legacy manifest builders, `RouteDeckApp`, and the flat manifest models remain
explicit-import compatibility surfaces for Corpus. They are not the current
authoring or package-readiness path and are not advertised through the root
golden `__all__` surface.

## Current Alpha Policy

- Python can be installed locally with `python -m pip install -e .`.
- LangGraph stays optional through `.[langgraph]`; importing `routedeck_core`
  does not import LangGraph.
- `packages/core` and `packages/react` build ESM JavaScript and declarations to
  `dist`, and package exports point only at that build output.
- `packages/testing` is private and contains test-only factories and harnesses.
- The root pnpm workspace is private; public release still requires clean-pack
  proof, notices, versioning, and the complete release gate.
- Top-level `react/` is a deprecated source-export package retained only because
  Corpus still installs it. It is not a publication candidate or a source for
  new applications.
- Framework packages contain no product API defaults, labels, identifiers,
  prompts, product state, or product runtime dependencies.

## Tests And Evidence

```powershell
python -m pytest tests/test_public_api.py tests/app tests/supervision -q
python -m pip install -e .
python -c "from routedeck_core import ApplicationSpec, FeatureSpec, CompiledRouteDeckApp, compile_app, bind_app, RouteDeckOperationRunner, RouteDeckSession; print(ApplicationSpec.__name__, FeatureSpec.__name__, CompiledRouteDeckApp.__name__, RouteDeckOperationRunner.__name__, RouteDeckSession.__name__)"
pnpm --filter @routedeck/core test
pnpm --filter @routedeck/react test
pnpm --filter @routedeck/testing test
pnpm typecheck
pnpm build
pnpm --dir packages/core pack --dry-run
pnpm --dir packages/react pack --dry-run
```

These are bounded package checks, not release proof. A public-release claim
requires the consolidated local release harness and its sanitized evidence.

## Update Triggers

Update this doc and `architecture/code-map.md` when changing package names,
versions, root exports, extras, workspace ownership, output formats, npm
privacy, notices, clean-pack policy, compatibility removal gates, or release
automation.
