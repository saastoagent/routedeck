# Public Source Publication And CI Closeout

Date: 2026-07-21
Repository: `https://github.com/saastoagent/routedeck`
Runtime for local validation: Windows, `D:\Dev\AI Projects\routedeck`

## Outcome

RouteDeck's current source is public under the SaaStoAgent organization. The
existing remote received the prepared public-alpha commit before the local
checkout was migrated to the SaaStoAgent repository as its sole remote. The
first public CI failure was corrected, and the replacement run completed
successfully.

This is a public source launch, not a PyPI/npm package release. No registry
package, trusted publisher, release tag, GitHub Release, or protected live-stack
reset is claimed.

## Publication Evidence

- Public-alpha commit:
  `7d71e4471778abdb5e44c7b642ac0e06227d1dbe` (`prepare RouteDeck public alpha`).
- Corrective commit:
  `6ec2d6d94009fdc1df98f2360b598775405d810c` (`fix first public CI bootstrap`).
- Commit identity:
  `Raghavendra Singh Dasila <raghavdasila@saastoagent.com>`.
- Canonical repository and sole configured remote at closeout:
  `https://github.com/saastoagent/routedeck.git`.
- Default branch: `main`, tracking `origin/main` at corrective commit closeout.
- Local untracked `artifacts/` evidence remained unpublished and untouched.

## CI Failure And Correction

Initial run:
`https://github.com/saastoagent/routedeck/actions/runs/29830983630`

Two clean-checkout failures were identified:

1. `context.md` linked to a local-only video under the intentionally
   unpublished `artifacts/` tree.
2. The Node 22.13 runner's bundled Corepack could not verify the current pnpm
   signing key.

The corrective commit removed the public link while retaining an honest local
evidence statement and changed CI to install the already-pinned `pnpm@11.7.0`
directly.

Successful replacement run:
`https://github.com/saastoagent/routedeck/actions/runs/29831749835`

- Head SHA: `6ec2d6d94009fdc1df98f2360b598775405d810c`.
- Status: completed.
- Conclusion: success.
- TypeScript job: install, tests, typechecks, builds, and public npm archive
  inspection passed.
- Python job: installation, non-live tests, Ruff/mypy, architecture and
  documentation contracts, and Python distribution inspection passed.

## Context Closeout Validation

```powershell
python scripts/check_doc_coverage.py
python scripts/check_context_architecture.py
python -m pytest tests/test_active_design_authority.py -q
```

Final result: documentation coverage mapped 596/596 maintained live files;
context architecture passed across 43 active Markdown files; authority tests
passed 4/4.

## Remaining Release Boundary

- Confirm ownership of the PyPI and npm package identities.
- Configure least-privilege trusted publishers.
- Choose first alpha versions and create the registry release source state.
- Publish and verify installs from PyPI/npm in clean consumers.
- Run the protected reset/full release harness only under separate approval.
