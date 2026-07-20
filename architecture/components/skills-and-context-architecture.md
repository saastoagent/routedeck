# Skills And Context Architecture

## Purpose

This component owns RouteDeck repo-local skills and RouteDeck-local context
architecture handoff files.

Skills capture stable repeatable procedures with clear invocation criteria,
inputs, outputs, checks, and stop conditions. They should not encode one-off
session history.

## Owner Files

- `skills/routedeck-feature-authoring/SKILL.md`
- `skills/routedeck-langgraph-integration/SKILL.md`
- `critical_prompt.md`
- `context.md`
- `context_pipeline.md`
- `instructions.md`
- `work_prompt.md`
- `structure.md`
- `SYSTEM_FLOW_INDEX.md`
- `architecture/feature-coverage.md`
- `architecture/documentation-map.md`
- `test_index/**/*`
- `logs/**/*`
- `context_checkpoints/**/*`
- `context_history/**/*`
- `plans/**/*`
- `decisions/**/*`
- `knowledgebase/**/*`
- `audits/**/*`
- `errors/**/*`

## Public Interfaces

- Repo-local RouteDeck skills.
- RouteDeck context restart files.
- Session start, closeout, checkpoint, and validation-index workflow.

## Dependent Flows

- RouteDeck session start and closeout.
- RouteDeck context/architecture retrofit.
- RouteDeck feature authoring.
- LangGraph integration.
- Closeout and code-reference maintenance.

## Tests And Evidence

- Skill self-review against trigger, input, output, check, and stop-condition rules.
- `python scripts/check_doc_coverage.py`
- `python scripts/check_doc_coverage.py --files critical_prompt.md`
- `python scripts/check_context_architecture.py`

## Update Triggers

Update this doc and `architecture/code-map.md` when changing:

- skill trigger rules
- skill folder names
- context file inventory
- handoff workflow assumptions
- advisory checker behavior
- archive classification or canonical feature coverage
