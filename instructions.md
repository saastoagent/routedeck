# Documentation Instructions - RouteDeck

Use this workflow whenever RouteDeck source, runtime behavior, architecture,
tests, examples, docs, or project state changes.

## Default Flow

1. Read `critical_prompt.md`, `context.md`, and `docs/route-deck-reference.md`.
2. Identify the subsystem row in `architecture/code-map.md`.
3. Make the smallest coherent change.
4. Run the relevant validation command from `test_index/README.md` or the
   code-map row.
5. Update component docs when interfaces, ownership, or invariants move.
6. Update `SYSTEM_FLOW_INDEX.md` only when runtime or UX flows change.
7. Update `context.md` as the concise restart state.

## Where Information Belongs

| Information | Location |
| --- | --- |
| Framework terms and payload meaning | `docs/route-deck-reference.md` |
| Current restart state | `context.md` |
| Session evidence | `logs/`, `context_checkpoints/` |
| Source ownership | `architecture/code-map.md` |
| Subsystem contracts | `architecture/components/` |
| User/developer guides | `docs/` |
| Test meaning and commands | `test_index/README.md` |
| Architectural decisions | `decisions/` |
| Reusable findings | `knowledgebase/` |
| Repeatable procedures | `skills/` |
| Debugging failures | `errors/` |

## Closeout Checklist

- Changed files are listed.
- Each changed source file maps to a code-map subsystem row.
- Related architecture/component docs are updated or explicitly unchanged.
- Related test docs are updated or explicitly unchanged.
- Validation commands and results are recorded.
- `context.md` links to current anchors instead of duplicating them.

## Skill Rule

Create a repo-local skill only when the workflow is stable, repeatable, and has
clear invocation criteria, inputs, outputs, checks, and stop conditions. Do not
create skills for one-off fixes or session-specific history.
