# Third-Party Notices

Runtime, optional, peer, build, and test dependencies are resolved through
Python and npm package managers and remain governed by their own licenses. The
standalone Medusa example also contains one adapted upstream seed source file,
described below.

Current dependency surfaces include:

- Python runtime: `pydantic`
- Python optional adapter: `langgraph`
- Python build backend: `hatchling`
- React peer dependencies: `react`, `react-dom`, `@xyflow/react`
- React package smoke tooling: npm package metadata and `npm pack --dry-run`
- Medusa demo server: exact Medusa `2.13.6` packages and a generated npm lock
- Local validation tooling: `pytest` and related plugins available in the
  development environment

## Adapted Medusa Starter Seed

`examples/medusa-agent/medusa/src/scripts/seed.ts` is adapted from the official
[`medusajs/medusa-starter-default`](https://github.com/medusajs/medusa-starter-default)
seed. The upstream package identifies Medusa as the author and declares the MIT
license. RouteDeck's adaptation preserves the store, region, fulfillment,
publishable-key, product, and inventory setup needed by the protected demo while
making the canonical data construction explicit and maintainable. The MIT
license text applying to RouteDeck and this adapted file is included in
`LICENSE`.

RouteDeck does not ship installed dependency trees, compiled third-party
bundles, database contents, generated credentials, or runtime manifests.
Package lockfiles are source-controlled dependency snapshots; the protected
Medusa catalog is an explicitly labeled local demo fixture and is created only
by the guarded provisioner.

Before any public release, refresh this notice against the locked dependency
set or published package manifests and include required upstream license texts
or links.
