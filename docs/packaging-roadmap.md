# Packaging Roadmap

RouteDeck is a local release candidate for its first open-source alpha. Its
clean-break package boundaries are implemented, package archives are checked by
`scripts/verify_release_archives.py`, and non-destructive CI is defined. Public
release remains unclaimed until the protected full release harness, external
namespace/trusted-publisher setup, authorized source-control release state, and
registry publication produce current evidence.

## Python Distribution

Candidate distribution: `routedeck-core`.

- `routedeck_core` stays dependency-light and product-neutral.
- LangGraph, FastAPI, SQLAlchemy adapters, and test support stay behind explicit
  extras.
- Importing `routedeck_core` must not import optional frameworks or product
  modules.
- `Application` selects product-owned `Feature` modules and the entry node.
- `compile_app(...)` resolves node-owned transitions, validates, and produces
  `CompiledApplication`.
- `FeatureBindings.merge(...)` composes feature implementations and rejects
  duplicate ownership.
- `bind_app(...)` requires exactly one handler/provider/guard implementation for
  each declared reference.

There is one public authoring/runtime contract. Removed manifest builders,
subclass runtimes, flat models, and topology-parity helpers are not importable.

```powershell
python -m pip install -e .
python -c "from routedeck_core import Application, Feature, CompiledApplication, compile_app, bind_app, RouteDeckOperationRunner, RouteDeckSession; print(Application.__name__, Feature.__name__, CompiledApplication.__name__, RouteDeckOperationRunner.__name__, RouteDeckSession.__name__)"
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

Production package builds use `tsconfig.build.json`; tests remain included in
typechecking but are excluded from `dist`. TypeScript build metadata is written
under the ignored root `.cache/`, not shipped in npm archives. Both public
package READMEs state that registry publication has not happened yet.

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

See [`docs/releasing.md`](releasing.md) for the human approval gates between a
local release candidate and external publication.
