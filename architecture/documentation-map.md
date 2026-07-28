# RouteDeck Documentation Map

Last updated: 2026-07-22

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
| 10 | `wiki/`, `docs/using-routedeck.md`, `docs/minimal-example.md`, and reference-app docs | Learning paths and developer guidance built on the contracts above. |

## Public Direction And Active Work

| Document | Owns | Authority boundary |
| --- | --- | --- |
| `ROADMAP.md` | Outcome-based public direction, milestone status, and non-goals. | Forward-looking only; it cannot establish implemented behavior or override source, ADRs, or canonical contracts. |
| `plans/README.md` and the linked active plan | Current approved implementation sequence and approval gates. | Execution aid only; archive it at completion and never use it to override accepted architecture. |
| `CHANGELOG.md` | User-visible released changes by published version. | Records releases only; unreleased intent belongs in the roadmap or active plan. |
| `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, and `SUPPORT.md` | Public participation, reporting, conduct, and support expectations. | Process guidance; no runtime or package contract authority. |

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

`wiki/` is current public learning material, not a second contract owner. It
must link back to the canonical reference for normative semantics and remain
source-publishable as a GitHub Wiki without changing the authority order.
`wiki-site/` is a local reader for that checked-in source. It does not fork the
wiki content or acquire contract authority.

## Generated And Local-Only Material

`.venv/`, `node_modules/`, caches, `dist/`, `graphify-out/`, and generated
contract output are not architectural authority. `artifacts/` contains run
evidence only. `codex_chats_and_memories/` is a local conversation archive and
is explicitly outside the product/documentation authority chain.

## Update Rule

Any feature or boundary change must update the feature matrix and its owning
code-map/component row. Any change to authority or lifecycle folders must also
update this map, `context_pipeline.md`, and the context-architecture component.
Roadmap changes must preserve the forward-looking classification above and link
to an ADR before presenting an architectural decision as accepted.
When an implementation spans several owners, keep one reusable
implementation-to-contract-to-proof crosswalk in `knowledgebase/` and link it
from the affected ADRs/canonical coverage rows instead of duplicating the same
file inventory across documents.
