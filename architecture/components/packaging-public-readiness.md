# Packaging And Public Readiness

## Purpose

This component owns RouteDeck's package metadata, public docs, release posture,
and readiness to become a credible public alpha.

## Owner Files

- `pyproject.toml`
- `react/package.json`
- `README.md`
- `docs/packaging-roadmap.md`
- `docs/*.md`

## Public Interfaces

- Python package `routedeck-core`.
- Optional Python extra `langgraph`.
- npm package `@routedeck/react`.
- Public README and docs.

## Dependent Flows

- Local sibling consumption from SaaStoAgent.
- Future PyPI/npm-style install.
- Public repo export or subtree split.
- CI/release automation.

## Tests And Evidence

- `python -m pytest tests -q`
- `cd react && npm test`
- packaging roadmap review

## Update Triggers

Update this doc and `architecture/code-map.md` when changing:

- package names, versions, exports, license, authors, URLs, or classifiers
- npm `private` flag or package export shape
- build/declaration output policy
- public docs or whitepaper claims
- CI/release automation
- public scrub/repo export plans
