# Third-Party Notices

RouteDeck does not vendor third-party source code in this repository. Runtime,
optional, peer, build, and test dependencies are resolved through Python and npm
package managers and remain governed by their own licenses.

Current dependency surfaces include:

- Python runtime: `pydantic`
- Python optional adapter: `langgraph`
- Python build backend: `hatchling`
- React peer dependencies: `react`, `react-dom`, `@xyflow/react`
- Local validation tooling: `pytest` and related plugins available in the
  development environment

Before any public release, refresh this notice against the locked dependency
set or published package manifests and include required upstream license texts
or links.
