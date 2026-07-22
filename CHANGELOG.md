# Changelog

All notable public changes to RouteDeck will be recorded here. The format is
based on Keep a Changelog; the project is currently pre-1.0 and does not yet
claim a published package release.

## Unreleased

### Added

- `RouteDeckBootstrapBoundary` and `useRouteDeckBootstrapRecovery` in
  `@routedeck/react`, exposing product-neutral bootstrap phases and only the
  recovery actions that are legal for the current RouteDeck store state.
- Public source repository under the SaaStoAgent organization with a green
  Python and TypeScript CI baseline.
- Public roadmap and project-health documentation.
- Clean release-archive verification for Python and npm packages.
- Non-destructive continuous-integration and dependency-update configuration.

### Changed

- npm production builds exclude test output and TypeScript build metadata.
- Package metadata now identifies the repository, license, support boundary,
  and alpha status.
- The release verifier uses the current Medusa compiler factory and boundary
  report schema.

### Security

- Added a private vulnerability-reporting policy and read-only CI permissions.
