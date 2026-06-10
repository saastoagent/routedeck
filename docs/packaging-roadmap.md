# Packaging Roadmap

RouteDeck is still a local alpha package. The package metadata is intentionally
close to publishable, but the release switch stays off until the examples,
public docs, and declaration/build output are repeatable.

## Python Package

Candidate package: `routedeck-core`

Runtime dependency policy:

- Keep `routedeck_core` dependency-light. `pydantic` is the only required
  runtime dependency.
- Keep LangGraph optional through the `langgraph` extra. LangGraph integrations
  live behind `routedeck_langgraph` and must not leak into core imports.
- Do not add product dependencies to the Python package.

Current public import surface:

- Manifest and static contract models: `RouteDeckManifest`,
  `RouteDeckNodeSpec`, `RouteDeckEdgeSpec`, `RouteDeckActionSpec`,
  `RouteDeckFieldSpec`, `RouteDeckCapabilitySpec`, `RouteDeckSensitivePolicy`
- Runtime/projection models: `RouteDeckProjection`, `RouteDeckRuntimeState`,
  `RouteDeckRuntimeSnapshot`, `RouteDeckOperation`, `RouteDeckSurface`,
  `RouteDeckNavigationState`, `RouteDeckLocation`, `RouteDeckDeepLink`
- Navgraph and surface binding models: `RouteDeckNavGraph`,
  `RouteDeckNavGraphNode`, `RouteDeckNavGraphEdge`,
  `RouteDeckAvailableEntity`, `RouteDeckEntityOperationBinding`,
  `RouteDeckSurfaceAffordance`, `RouteDeckBindingExpression`,
  `RouteDeckSurfaceInteractionEvent`
- Event and diagnostics models: `RouteDeckEvent`, `RouteDeckDispatchInput`,
  `RouteDeckDispatchResult`, `RouteDeckIntrospection`,
  `RouteDeckSemanticObservation`
- Helpers and protocols: `RouteDeckRuntime`, `validate_manifest()`,
  `build_projection()`, `build_runtime_snapshot()`,
  `build_dispatch_state_event()`, `reachable_nodes()`

Smoke command:

```powershell
python -m pip install -e .
python -c "from routedeck_core import RouteDeckManifest, RouteDeckProjection; print(RouteDeckManifest.__name__, RouteDeckProjection.__name__)"
```

## React Package

Candidate package: `@routedeck/react`

Current export policy:

- Exports are source TypeScript files through `exports["."]`.
- `types` points to `src/index.ts` for local source-consuming workspaces.
- This is acceptable for the local alpha, but a public npm release should add a
  build step that emits ESM JavaScript and declaration files.

Current public import surface:

- Store APIs: `createRouteDeckStore`, `createStaticRouteDeckStore`
- Provider and hooks: `RouteDeckProvider`, `useRouteDeckProjection`,
  `useRouteDeckState`, `useRouteDeckStatus`, `useRouteDeckDispatch`,
  `useRouteDeckInspect`, `useRouteDeckCapabilities`,
  `useRouteDeckAvailableEntities`, `useRouteDeckSurfaceAffordances`,
  `useRouteDeckNavigation`, and related hook exports
- Surface and debugger utilities: `RouteDeckSurfaceHost`,
  `resolveRouteDeckActiveSurface`, `RouteDeckDebugger`
- Navigation helpers: `createBrowserRouteDeckHistoryAdapter`,
  `readRouteDeckHistoryLocation`, `writeRouteDeckHistoryLocation`,
  `routeDeckUrlString`
- Operation readiness helpers: `isRouteDeckOperationDispatchable`,
  `routeDeckAssistantActions`, `routeDeckOperationInteraction`
- Type contracts from `src/types.ts`

Peer dependency policy:

- Keep `react`, `react-dom`, and `@xyflow/react` as peer dependencies.
- Do not bundle React, React DOM, or debugger rendering peers into the package.
- Do not add product-specific runtime dependencies.

`private: true` can be removed only after all of these are true:

- The package has a stable build/declaration output policy.
- `npm pack --dry-run` contains only intended public package files.
- React tests and product-neutral example tests pass from a clean install path.
- README and package metadata describe source-export or build-output behavior
  honestly.
- `THIRD_PARTY_NOTICES.md` has been refreshed against the exact dependency set.

Smoke command:

```powershell
cd react
npm test
npm pack --dry-run
```

## Release Checklist

Before any public release:

- Run the Python and React smoke commands above.
- Run the product-neutral example commands in `docs/minimal-example.md`.
- Run `python scripts/check_doc_coverage.py` and explain any advisory warning.
- Confirm package files do not include product-specific examples unless they are
  explicitly published as downstream product examples.
- Confirm `LICENSE` and `THIRD_PARTY_NOTICES.md` match the published package
  contents.
- Add a changelog entry and semantic versioning note.

## Contract Compatibility

RouteDeck preserves a stable JSON shape for manifests, projections, runtime
state, events, navgraph, surface affordances, and dispatch envelopes. Products
may add domain data inside sanctioned metadata, props, graph state, and context
fields, but framework packages must remain product-neutral.
