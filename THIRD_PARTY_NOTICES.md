# Third-Party Notices

RouteDeck does not vendor third-party source code in this repository. Runtime,
optional, peer, build, and test dependencies are resolved through Python and npm
package managers and remain governed by their own licenses.

Current dependency surfaces include:

- Python runtime: `pydantic`
- Python optional adapter: `langgraph`
- Python build backend: `hatchling`
- React peer dependencies: `react`, `react-dom`, `@xyflow/react`
- React package smoke tooling: npm package metadata and `npm pack --dry-run`
- Local validation tooling: `pytest` and related plugins available in the
  development environment

RouteDeck does not currently ship built third-party assets, vendored source,
compiled bundles, generated dependency snapshots, or product-specific runtime
fixtures inside the package allowlists. The React package dry-run currently
ships source files from `react/src` and package metadata only.

Before any public release, refresh this notice against the locked dependency
set or published package manifests and include required upstream license texts
or links.
