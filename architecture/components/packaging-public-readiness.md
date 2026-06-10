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

## Current Alpha Policy

- Python core can be installed locally with `python -m pip install -e .`.
- The LangGraph adapter remains optional through `.[langgraph]`.
- The React package intentionally exports source TypeScript during the local
  alpha. A public npm release needs a build/declaration output policy first.
- `react/package.json` keeps `private: true` until package contents,
  declaration output, and notices are release-ready.
- Framework packages must not include product-specific API defaults, product
  labels, product ids, or product runtime dependencies.

## Dependent Flows

- Local sibling consumption from downstream product repositories.
- Future PyPI/npm-style install.
- Public repo export or subtree split.
- CI/release automation.

## Tests And Evidence

- `python -m pytest tests -q`
- `cd react && npm test`
- `python -m pip install -e .`
- `python -c "from routedeck_core import RouteDeckManifest, RouteDeckProjection; print(RouteDeckManifest.__name__, RouteDeckProjection.__name__)"`
- `cd react && npm pack --dry-run`
- packaging roadmap review

## Update Triggers

Update this doc and `architecture/code-map.md` when changing:

- package names, versions, exports, license, authors, URLs, or classifiers
- npm `private` flag or package export shape
- build/declaration output policy
- public docs or whitepaper claims
- CI/release automation
- public scrub/repo export plans
