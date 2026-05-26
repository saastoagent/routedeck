# Skills And Context Architecture

## Purpose

This component owns RouteDeck repo-local skills and the generic
`context_architecture_bundle` starter kit.

Skills capture stable repeatable procedures with clear invocation criteria,
inputs, outputs, checks, and stop conditions. They should not encode one-off
session history.

## Owner Files

- `skills/routedeck-manifest-authoring/SKILL.md`
- `skills/routedeck-manifest-scaffolder/SKILL.md`
- `skills/routedeck-manifest-scaffolder/scripts/scaffold_manifest.py`
- `skills/routedeck-langgraph-integration/SKILL.md`
- `context_architecture_bundle/**/*`

## Public Interfaces

- Repo-local RouteDeck skills.
- Context architecture starter kit templates.
- Starter-kit skills:
  - create a complete context architecture bundle from a project idea/spec
  - populate context architecture for an existing codebase

## Dependent Flows

- New project bootstrapping.
- Existing project context/architecture retrofit.
- RouteDeck manifest authoring.
- LangGraph integration.
- Closeout and code-reference maintenance.

## Tests And Evidence

- Skill self-review against trigger, input, output, check, and stop-condition rules.
- `python context_architecture_bundle/scripts/check_doc_coverage.py --help`
- `python skills/routedeck-manifest-scaffolder/scripts/scaffold_manifest.py skills/routedeck-manifest-scaffolder/examples/basic-flow.json generated_manifest.py --force`

## Update Triggers

Update this doc and `architecture/code-map.md` when changing:

- skill trigger rules
- skill folder names
- bundle template inventory
- starter-kit workflow assumptions
- advisory checker behavior
- scaffolder inputs or outputs
