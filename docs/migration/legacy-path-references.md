# Legacy Path References

RouteDeck now runs from the root of this standalone repository. Active code,
package metadata, Compose configuration, and runtime scripts do not depend on
the former `agent-core` checkout or its `agent-lab-powered-projects` layout.

The following old-path matches are intentionally preserved as historical or
migration evidence and must not be executed as current instructions:

| Evidence family | Files | Matches | Reason retained |
| --- | ---: | ---: | --- |
| `context_checkpoints/` | 2 | 7 | Immutable session checkpoints |
| `context_history/` | 2 | 6 | Immutable archived context |
| `docs/superpowers/plans/` | 9 | 112 | Completed implementation plans and provenance |
| `docs/migration/source-baseline.md` | 1 | 2 | Extraction source and filter-path evidence |

Two current-document/code matches are intentional and are not dependencies:

- `examples/medusa-agent/README.md` states that the example does **not** need
  the old `agent-core/test_targets` checkout.
- `scripts/check_boundaries.py` rejects any future Compose dependency whose
  path contains `test_targets`.

`docs/propertydesk-reference-app.md` was updated during extraction so its
current location examples are repository-relative.
