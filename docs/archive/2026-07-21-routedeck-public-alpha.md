# RouteDeck Public Alpha Implementation Plan

Status: completed and archived after the public source launch and first green
GitHub Actions run on 2026-07-21. This plan is historical evidence; current
state lives in `context.md`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare the implemented RouteDeck feature set for an honest,
installable, reproducible open-source alpha without adding runtime or Medusa
product behavior.

**Architecture:** Keep RouteDeck's current Python distribution with explicit
adapter extras and its two public TypeScript packages. Repair release truth,
build clean artifacts, add public project governance and non-destructive CI,
and document the outcome-based public roadmap while preserving the existing
ADR and canonical-contract authority chain.

**Tech Stack:** Python 3.11+, Hatchling, pytest, Ruff, mypy, TypeScript, pnpm
11.7.0, Vitest, GitHub Actions, PyPI and npm package metadata.

## Global Constraints

- Work only in `D:\Dev\AI Projects\routedeck` on local Windows.
- Do not perform Git operations unless the user separately authorizes them.
- The intended canonical repository is `https://github.com/saastoagent/routedeck`.
  When Git work is separately authorized, use the repository-scoped commit
  email `raghavdasila@saastoagent.com`.
- Do not claim GitHub, npm, or PyPI identities or publish external state.
- Do not run the protected release reset or start the Medusa/browser stack.
- Do not add RouteDeck runtime, Medusa product, authentication, protocol, or
  observability features in M0.
- Missing tools, dependencies, credentials, evidence, or package invariants
  fail loudly; no fixture or fallback may satisfy a release claim.
- `ROADMAP.md` is forward-looking public direction, not architecture or
  implementation authority.

---

### Task 1: Public roadmap and documentation ownership

**Files:**

- Create: `ROADMAP.md`
- Modify: `architecture/documentation-map.md`
- Modify: `architecture/code-map.md`
- Modify: `architecture/components/packaging-public-readiness.md`
- Modify: `plans/README.md`
- Test: `scripts/check_doc_coverage.py`
- Test: `scripts/check_context_architecture.py`

**Interfaces:**

- Consumes: the product identity in `critical_prompt.md` and M0-M3 direction
  approved on 2026-07-21.
- Produces: one public roadmap explicitly subordinate to current source, ADRs,
  and canonical contracts.

- [x] Write `ROADMAP.md` with vision, principles, M0-M3 outcomes, non-goals,
  status, and roadmap-change policy.
- [x] Classify the roadmap as forward-looking guidance in the documentation
  map.
- [x] Add roadmap and public-health files to the packaging/public ownership
  row and component owner list.
- [x] Run documentation and context-architecture checks and fix every mapping
  or link violation.

### Task 2: Current release-contract repair

**Files:**

- Modify: `tests/test_release_harness.py`
- Modify: `examples/medusa-agent/scripts/release-summary.py`
- Modify: `examples/medusa-agent/scripts/release-verify.ps1`
- Test: `tests/test_boundary_report.py`
- Test: `tests/test_boundary_rules.py`

**Interfaces:**

- Consumes: `scripts.check_boundaries.BOUNDARY_REPORT_SCHEMA_VERSION == 4`
  and `medusa_agent.composition:compile_medusa_app`.
- Produces: a release summary and verifier that accept exactly the current
  boundary schema and public Medusa compiler factory.

- [x] Change the release-harness test to require schema 4 and the exact current
  factory name, then run it against the stale implementation to prove failure.
- [x] Update the release summary to schema 4 and update the verifier factory
  reference without adding compatibility aliases.
- [x] Run the focused release/boundary tests and generate a fresh temporary
  schema-4 boundary report with zero violations.

### Task 3: Clean Python distribution

**Files:**

- Modify: `pyproject.toml`
- Modify: `tests/test_public_api.py`
- Modify: `examples/medusa-agent/scripts/release-verify.ps1`
- Modify: `THIRD_PARTY_NOTICES.md`
- Create: `scripts/verify_release_archives.py`
- Create: `tests/test_release_archives.py`

**Interfaces:**

- Consumes: the user-designated public repository URL
  `https://github.com/saastoagent/routedeck` and the current Hatchling package
  list.
- Produces: metadata-complete wheel/sdist contents and clean installation proof
  from the built wheel rather than from the source directory.

- [x] Add repository, documentation, issue-tracker, typing, supported-version,
  and alpha-status metadata without changing package names or dependencies.
- [x] Add archive verification that rejects caches, tests, runtime data,
  credentials, examples, and unexpected top-level package paths.
- [x] Change the clean-install release step to install the freshly built wheel
  plus the Medusa example, not `.[...]` from the copied source tree.
- [x] Build, inspect, install in a temporary virtual environment, and import
  every advertised Python package.

### Task 4: Clean npm distributions

**Files:**

- Modify: `packages/core/package.json`
- Modify: `packages/react/package.json`
- Modify: `packages/core/tsconfig.json`
- Modify: `packages/react/tsconfig.json`
- Create: `packages/core/tsconfig.build.json`
- Create: `packages/react/tsconfig.build.json`
- Create: `packages/core/README.md`
- Create: `packages/react/README.md`
- Modify: `examples/medusa-agent/scripts/release-verify.ps1`
- Test: `tests/test_release_archives.py`

**Interfaces:**

- Consumes: `@routedeck/core` and `@routedeck/react` public exports.
- Produces: npm tarballs containing runtime JavaScript, declarations, intended
  maps, package metadata, README, and license, with no compiled tests or
  `.tsbuildinfo`.

- [x] Add complete public package metadata and package-local README files.
- [x] Separate test-aware typechecking from production builds so tests remain
  checked but do not enter `dist`.
- [x] Move TypeScript build info outside `dist` and update build scripts.
- [x] Pack both packages into a temporary directory, inspect exact contents,
  install the tarballs into a clean consumer workspace, and verify TypeScript
  imports/build.

### Task 5: Public project health and non-destructive CI

**Files:**

- Create: `CONTRIBUTING.md`
- Create: `SECURITY.md`
- Create: `CODE_OF_CONDUCT.md`
- Create: `SUPPORT.md`
- Create: `CHANGELOG.md`
- Create: `docs/releasing.md`
- Create: `.github/workflows/ci.yml`
- Create: `.github/dependabot.yml`
- Create: `.github/ISSUE_TEMPLATE/bug_report.yml`
- Create: `.github/ISSUE_TEMPLATE/feature_request.yml`
- Create: `.github/pull_request_template.md`

**Interfaces:**

- Consumes: existing local validation commands and official GitHub Actions for
  checkout, Python setup, and Node setup.
- Produces: public contribution/security/release contracts and a read-only CI
  workflow with no credentials, publishing, protected reset, Docker services,
  or live-model dependency.

- [x] Add project-health documents with explicit alpha support, vulnerability
  reporting, conduct enforcement, and contribution boundaries.
- [x] Add Windows CI using only official GitHub actions, read-only token
  permissions, Python 3.11, Node 22.13.0, pnpm 11.7.0, and frozen lockfiles.
- [x] Add weekly Dependabot groups for GitHub Actions, pip, and pnpm without
  automerge.
- [x] Add structured bug, feature, and pull-request templates that require
  reproduction, proof boundary, and source-of-truth declarations.
- [x] Parse the workflow and Dependabot YAML locally and run every CI command
  outside GitHub.

### Task 6: Public adoption and release documentation

**Files:**

- Modify: `README.md`
- Modify: `docs/packaging-roadmap.md`
- Modify: `test_index/README.md`
- Modify: `architecture/components/examples-and-adoption.md`
- Modify: `context.md`
- Modify: `structure.md`

**Interfaces:**

- Consumes: current package names, current Medusa quickstart, public roadmap,
  and archive-verification commands.
- Produces: an external-user path from project purpose through source install,
  package status, current proof, limitations, roadmap, and release process.

- [x] Lead the README with RouteDeck's application-state and interaction-
  governance value, then show ownership, source install, minimal authoring,
  Medusa proof, limitations, and contribution links.
- [x] Keep registry install commands explicitly unavailable until packages are
  actually published; do not make future package availability look current.
- [x] Update packaging, test, adoption, and structure docs with exact artifact
  and CI proof boundaries.
- [x] Refresh `context.md` to make public-alpha preparation the active work and
  preserve all previously proven runtime evidence as dated evidence only.

### Task 7: Non-destructive release-candidate verification

**Files:**

- Create: `logs/2026-07-21-public-alpha-boundary-1.md`
- Modify: `context.md`

**Interfaces:**

- Consumes: every local M0 artifact and validation command from Tasks 1-6.
- Produces: one exact local verification record and an explicit list of the
  remaining external, protected-reset, Git, and publication approval gates.

- [x] Run focused release, public API, boundary, documentation, package test,
  typecheck, build, dry-pack, built-artifact install, and source-scrub checks.
- [x] Record exact commands, counts, archive inventories, output paths, and any
  unverified behavior in the session log.
- [x] Update current context with the true M0 status; do not claim public
  release or live release proof.
- [x] Stop before namespace claims, trusted-publisher setup, protected reset,
  Git operations, repository visibility changes, or registry publication.
