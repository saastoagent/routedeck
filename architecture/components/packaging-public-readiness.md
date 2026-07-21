# Packaging And Public Readiness

## Purpose

This component owns package metadata, canonical imports, release posture, and
readiness evidence for the Python framework plus the `packages/core`,
`packages/react`, and `packages/testing` workspace.

## Owner Files

- `pyproject.toml`, `package.json`, and `pnpm-workspace.yaml`
- `packages/*/package.json`, `packages/*/README.md`, package build configs, and
  `packages/*/src/index.ts`
- `routedeck_core/__init__.py`
- `README.md`, `ROADMAP.md`, public project-health files, `.github/`,
  `docs/packaging-roadmap.md`, and `docs/releasing.md`

## Public Interfaces

- Python `routedeck-core` with explicit optional extras.
- `Application`, `Feature`, `CompiledApplication`, `compile_app(...)`,
  `FeatureBindings`, and `bind_app(...)`.
- Runner/session/event/projection contracts including
  `RouteDeckOperationRunner`, `RouteDeckSession`, `RouteDeckEvent`, and
  `RouteDeckSessionStore`.
- `@routedeck/core` and `@routedeck/react`.
- Private test-support package `@routedeck/testing`.
- `ROADMAP.md` as non-authoritative public direction and the root
  contribution/security/support contracts.

Removed APIs are absent rather than redirected. Framework packages contain no
product prompts, endpoints, identifiers, runtime data, or product dependencies.

## Evidence

```powershell
python -m pytest tests/test_public_api.py tests/app tests/supervision -q
pnpm --filter @routedeck/core test
pnpm --filter @routedeck/react test
pnpm --filter @routedeck/testing test
pnpm typecheck
pnpm build
pnpm --dir packages/core pack --dry-run
pnpm --dir packages/react pack --dry-run
```

These are bounded package checks. A public-release claim requires the complete
local release harness and sanitized evidence.
