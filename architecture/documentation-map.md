# RouteDeck Documentation Map

Last updated: 2026-07-20

This map prevents historical implementation material from competing with live
architecture. When documents disagree, use the highest applicable row below.

## Canonical Documents

| Order | Document | Owns |
| ---: | --- | --- |
| 1 | `critical_prompt.md` | Product identity, invariants, authority chain, stop conditions. |
| 2 | `context.md` | Concise current state, known gaps, and next step. |
| 3 | `decisions/ADR-006...`, then non-superseded ADR-005 and ADR-004 | Durable architectural decisions. |
| 4 | `docs/route-deck-reference.md` | Framework vocabulary and contract semantics. |
| 5 | `architecture/feature-coverage.md` | Complete feature-to-owner/code/doc/test matrix. |
| 6 | `architecture/code-map.md` and `architecture/components/` | Source ownership and subsystem maintenance contracts. |
| 7 | `SYSTEM_FLOW_INDEX.md` | Current runtime, conversation, operation, navigation, and bootstrap sequences. |
| 8 | `test_index/README.md` | Validation commands and the claims they can support. |
| 9 | `structure.md` | Maintained live source tree and dependency direction. |
| 10 | `docs/using-routedeck.md`, `docs/minimal-example.md`, and reference-app docs | Developer guidance built on the contracts above. |

## Historical But Retained

| Location | Meaning |
| --- | --- |
| `docs/archive/` | Superseded plans/designs, old concepts, completed reports, handoffs, and whitepaper material. |
| `decisions/ADR-001...` through historical portions of later ADRs | Decision history; status/supersession text controls. |
| `context_history/` | Prior `context.md` snapshots. |
| `context_checkpoints/` | Session handoffs; only the newest dated checkpoint is relevant to resume. |
| `logs/` | Completed session evidence. |
| `audits/` | Point-in-time read-only findings. |
| `docs/migration/` | Extraction and source provenance. |
| `errors/` | Resolved debugging evidence. |
| `knowledgebase/` | Reusable verified findings and implementation crosswalks; subordinate to the canonical spine and current source. |

Historical material never overrides current source or the canonical spine. Its
commands, paths, API names, and status may intentionally describe an older
state.

## Generated And Local-Only Material

`.venv/`, `node_modules/`, caches, `dist/`, `graphify-out/`, and generated
contract output are not architectural authority. `artifacts/` contains run
evidence only. `codex_chats_and_memories/` is a local conversation archive and
is explicitly outside the product/documentation authority chain.

## Update Rule

Any feature or boundary change must update the feature matrix and its owning
code-map/component row. Any change to authority or lifecycle folders must also
update this map, `context_pipeline.md`, and the context-architecture component.
When an implementation spans several owners, keep one reusable
implementation-to-contract-to-proof crosswalk in `knowledgebase/` and link it
from the affected ADRs/canonical coverage rows instead of duplicating the same
file inventory across documents.
