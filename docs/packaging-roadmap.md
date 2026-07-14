# Packaging Roadmap

RouteDeck is a local alpha. Its clean-break package boundaries are implemented;
public release remains open until clean-install, clean-pack, notices, and the
consolidated release harness produce current evidence.

## Python Distribution

Candidate distribution: `routedeck-core`.

- `routedeck_core` stays dependency-light and product-neutral.
- LangGraph, FastAPI, SQLAlchemy adapters, and test support stay behind explicit
  extras.
- Importing `routedeck_core` must not import optional frameworks or product
  modules.
- `ApplicationSpec` composes product-owned `FeatureSpec` modules.
- `compile_app(...)` validates and produces `CompiledRouteDeckApp`.
- `FeatureBindings.merge(...)` composes feature implementations and rejects
  duplicate ownership.
- `bind_app(...)` requires exactly one handler/provider/guard implementation for
  each declared reference.

There is one public authoring/runtime contract. Removed manifest builders,
subclass runtimes, flat models, and topology-parity helpers are not importable.

```powershell
python -m pip install -e .
python -c "from routedeck_core import ApplicationSpec, FeatureSpec, CompiledRouteDeckApp, compile_app, bind_app, RouteDeckOperationRunner, RouteDeckSession; print(ApplicationSpec.__name__, FeatureSpec.__name__, CompiledRouteDeckApp.__name__, RouteDeckOperationRunner.__name__, RouteDeckSession.__name__)"
python -m pytest tests/test_public_api.py tests/app -q
```

## TypeScript Workspace

- `packages/core` -> `@routedeck/core`: generated contracts, strict HTTP/SSE
  client, replay/resync, observable state/actions/selectors, routing/history,
  and private-form memory state.
- `packages/react` -> `@routedeck/react`: provider/hooks, surface host,
  navigation, operations, private forms, review, status, and navgraph.
- `packages/testing` -> private `@routedeck/testing`: factories and harnesses
  that never enter runtime paths.

No second React package exists. `packages/core` and `packages/react` export ESM
JavaScript and declarations from `dist`; the root workspace and testing package
remain private.

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

## Release Checklist

- Run the focused Python public-API/compiler/runner checks.
- Run workspace tests, typecheck, build, and dry-pack checks from a clean install.
- Run `python scripts/check_doc_coverage.py` and review every advisory.
- Verify archives contain only intended framework sources/build output and no
  credentials, runtime data, or product code.
- Refresh notices, changelog, and version notes against exact package contents.
- Complete the protected local release harness and inspect its sanitized proof
  bundle. Missing real integration access is a blocker, never a reason to
  substitute product behavior.
