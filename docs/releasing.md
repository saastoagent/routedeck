# Releasing RouteDeck

RouteDeck has not yet been published to PyPI or npm. This document separates
local release-candidate proof from external publication.

## Release Candidate

From a clean local Windows checkout with the documented Python, Node, pnpm,
Docker, Medusa, browser, and model prerequisites:

1. Run focused unit, boundary, documentation, typecheck, build, and archive
   checks.
2. Build the Python wheel and sdist and the two public npm tarballs.
3. Verify archive contents with `scripts/verify_release_archives.py`.
4. Install the built artifacts in isolated temporary environments and import
   or compile against their public entry points.
5. With separate approval for the protected demo reset, run the complete local
   release harness and inspect its sanitized evidence bundle.

The full harness is destructive to its protected local demo volumes. It must
not run in ordinary CI and must not be run without the explicit reset approval
required by the demo scripts.

## Publication Gates

Publication requires separate human approval for every external or destructive
action:

- confirm package names and repository visibility;
- choose versions and update this changelog;
- configure PyPI and npm trusted publishers with least privilege;
- complete and review the full release evidence;
- configure the repository-scoped commit email as
  `raghavdasila@saastoagent.com` when the Git release work is authorized;
- create the authorized source-control release state;
- publish to registries and verify installs from the registries themselves.

CI validates source and artifacts but contains no publishing job, registry
token, demo reset, Docker service startup, or live-model call. A successful CI
run is not a release claim.

## Failure Semantics

Missing credentials, integrations, package artifacts, or proof stop the
release. Do not substitute cached output, fixtures, alternate providers, or
scripted model behavior for a real release gate.
