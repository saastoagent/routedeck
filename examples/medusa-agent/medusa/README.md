# RouteDeck Medusa Demo Server

This directory is the complete Medusa server source used by the standalone
buyer-agent example. Compose builds only this repo-local context; no sibling
checkout, generated runtime data, secret, or installed dependency tree is
required.

The dependency graph is locked by `package-lock.json`. Medusa is pinned to
`2.13.6`, the Docker base is pinned by Node version and multi-platform digest,
and `pg` is a direct dependency because the protected provisioner imports it.
The server fails when required database, Redis, CORS, or secret configuration is
missing.

`src/scripts/seed.ts` is the Medusa starter seed adapted as the canonical
RouteDeck demo seed. The protected provisioner in `../infra` is its only normal
entrypoint: it verifies an empty or exact canonical database, runs the seed once,
emits the manifest, and creates the sentinel. Do not run the seed against an
unscoped database.

Source attribution and license details are recorded in the repository-level
`THIRD_PARTY_NOTICES.md`.
