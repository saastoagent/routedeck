# Packaging Roadmap

RouteDeck is a local alpha. Its current package boundaries are implemented, but
public release remains open until clean-install, clean-pack, notices, and the
consolidated release harness produce current evidence.

## Python Distribution

Candidate distribution: `routedeck-core`

Runtime dependency policy:

- Keep `routedeck_core` dependency-light and product-neutral. Pydantic and JSON
  Schema validation are the required runtime dependencies.
- Keep LangGraph, FastAPI, SQLite encryption, and test support behind their
  explicit extras.
- Importing `routedeck_core` must not import optional frameworks or product
  modules.

Current golden authoring surface:

- `ApplicationSpec` composes product-owned `FeatureSpec` modules.
- `compile_app(...)` produces a `CompiledRouteDeckApp` and fails on invalid
  routes, references, outcomes, or contract branches.
- `bind_app(...)` binds product providers, guards, context providers, and
  operation handlers without moving product behavior into the framework.
- `RouteDeckOperationRunner`, `RouteDeckSession`, `RouteDeckSessionStore`, and
  public projection/event contracts define the runtime boundary.

Smoke commands:

```powershell
python -m pip install -e .
python -c "from routedeck_core import ApplicationSpec, FeatureSpec, CompiledRouteDeckApp, compile_app, bind_app, RouteDeckOperationRunner, RouteDeckSession, RouteDeckSessionStore; print(ApplicationSpec.__name__, FeatureSpec.__name__, CompiledRouteDeckApp.__name__, RouteDeckOperationRunner.__name__, RouteDeckSession.__name__, RouteDeckSessionStore.__name__)"
python -m pytest tests/test_public_api.py tests/app -q
```

The flat `RouteDeckManifest`, `RouteDeckManifestBuilder`, `RouteDeckApp`,
decorator helpers, and `validate_manifest(...)` remain explicitly importable
only for active Corpus compatibility. They are excluded from the root golden
`__all__` surface and must not appear in a new-application or readiness
workflow.

## TypeScript Workspace

The authoritative workspace packages are:

- `packages/core` -> `@routedeck/core`: generated contracts, strict HTTP/SSE
  client, retained replay, observable state/actions/selectors, routing and
  exact history control, and private-form memory state.
- `packages/react` -> `@routedeck/react`: provider/hooks, surface registry and
  host, navigation, operation controller, private forms, review, status, and
  lazy inspector primitives.
- `packages/testing` -> private `@routedeck/testing`: factories and component,
  store, and SSE harnesses that never enter product runtime paths.

`packages/core` and `packages/react` export ESM JavaScript plus declarations
from `dist`. The root workspace and `@routedeck/testing` remain private.

Package checks:

```powershell
pnpm install --frozen-lockfile
pnpm --filter @routedeck/core test
pnpm --filter @routedeck/react test
pnpm --filter @routedeck/testing test
pnpm typecheck
pnpm build
pnpm --dir packages/core pack --dry-run
pnpm --dir packages/react pack --dry-run
```

## Legacy React Compatibility Quarantine

Top-level `react/` is not the current React package even though it temporarily
shares the npm name `@routedeck/react`. It is a deprecated, private,
source-export compatibility tree used by Corpus only. New applications import
the built packages from `packages/core` and `packages/react`.

Do not publish, link, or use top-level `react/` in a readiness workflow. Its
removal gate is explicit in `react/README.md`: Corpus must migrate and focused
compatibility/parity proof must pass before that directory can be deleted.

## Release Checklist

Before any public release:

- Run the Python smoke and focused compiler/public-API checks above.
- Run workspace tests, typecheck, build, and dry-pack checks from a clean
  install path.
- Run `python scripts/check_doc_coverage.py` and explain every advisory.
- Verify package archives contain only intended framework sources/build output
  and no product credentials, runtime data, or unapproved product code.
- Refresh `LICENSE`, `THIRD_PARTY_NOTICES.md`, changelog, and semantic version
  notes against the exact package contents.
- Complete the protected local release harness and review its sanitized proof
  bundle. Absence of required real integration credentials is a blocker, not a
  reason to substitute a fixture or fallback.

## Compatibility Policy

Compatibility facades preserve current consumers while they migrate; they do
not define the new authoring architecture. Removal requires an identified
consumer migration, focused parity evidence, and an approved removal change.
Current compiler, runner, durable session, event, projection, and frontend
contracts remain product-neutral and fail loudly when required dependencies or
invariants are unavailable.
