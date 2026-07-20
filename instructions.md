# Documentation Instructions - RouteDeck

Use this workflow whenever source, runtime behavior, architecture, tests,
examples, public guidance, or project state changes.

## Default Flow

1. Read `critical_prompt.md`, `context.md`, and
   `docs/route-deck-reference.md`.
2. Locate the capability in `architecture/feature-coverage.md` and source owner
   in `architecture/code-map.md`.
3. Read the owning component contract and validation row.
4. Make the smallest coherent change.
5. Update contract/flow/ownership/test docs only where meaning moved.
6. Run focused validation; do not infer broader pass status.
7. Close with a log, checkpoint, archived prior context when needed, and a
   concise current `context.md`.

## Information Placement

| Information | Location |
| --- | --- |
| Product identity, invariants, authority | `critical_prompt.md` |
| Framework terms and payload meaning | `docs/route-deck-reference.md` |
| Complete feature/owner/code/doc/test coverage | `architecture/feature-coverage.md` |
| Source ownership | `architecture/code-map.md` |
| Subsystem contracts | `architecture/components/` |
| Runtime/UX sequences | `SYSTEM_FLOW_INDEX.md` |
| Current restart state and known gaps | `context.md` |
| Validation meaning and commands | `test_index/README.md` |
| User/developer guides | current `docs/*.md` |
| Durable architectural choices | `decisions/` |
| Active decision-complete work | `plans/` or current `docs/superpowers/` record |
| Completed/superseded planning and reports | `docs/archive/` |
| Session evidence | `logs/`, `context_checkpoints/`, `context_history/` |
| Audits/provenance/debugging | owning lifecycle folder |
| Reusable verified cross-owner implementation trace | `knowledgebase/` |
| Stable repeatable procedures | `skills/` |

## Archive Rule

Archive material must remain visibly historical and must not appear in the
canonical start chain. Preserve accepted ADRs and unique evidence. Delete only
material proven to have no live source, package, import, test, or historical
value.

## Closeout Checklist

- Every changed live source maps to a feature and code-map row.
- Contract/ownership/flow/test changes are documented, or explicitly unchanged.
- Cross-owner behavior is represented once in a verified knowledgebase
  implementation crosswalk; file mapping alone is not semantic coverage.
- Canonical docs contain no retired API names or active links to archived plans.
- Documentation coverage and context/link authority checks pass.
- Validation commands/results and any blocker are recorded.
- `context.md` remains concise and links to durable detail.

## Skill Rule

Create or retain a repo-local skill only for a stable repeatable procedure with
clear triggers, inputs, outputs, checks, and stop conditions. Rename or delete a
skill when its vocabulary/API no longer exists; do not preserve compatibility
instructions.
