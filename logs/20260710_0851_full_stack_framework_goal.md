# 2026-07-10 08:51 IST - RouteDeck Full-Stack Framework Goal

## Summary

Locked RouteDeck's next framework architecture after the Corpus contract cleanup.
RouteDeck will support two developer modes through one shared kernel:

- Full Flow for ordinary developers and agent-assisted/vibe coders
- Core Integration for advanced developers with existing agents/custom graphs

## Decisions

- RouteDeck is a LangGraph-native full-stack agentic application framework, not
  only a projection or UI helper.
- Corpus is a consuming application definition and product implementation.
- Full Flow is the shared kernel plus the RouteDeck LangGraph compiler.
- Core Integration is the same kernel plus an executor adapter.
- RouteDeck owns one typed event architecture with explicit assistant, runtime,
  tool, surface, and diagnostic channels.
- Filtered and multiplexed SSE views share ordering, correlation, terminal, and
  replay semantics without collapsing visibility boundaries.
- Framework readiness requires two standalone examples independent of Corpus.
- One application specification exports the frontend contract; frontends keep
  only product component registration and copy.
- Dispatch is claimed before executor side effects, and a durable transactional
  SQLite backend provides state/result/event outbox and replay for the golden
  path. Interrupted external work is explicit; no false exactly-once claim is
  made.

## Documentation Updated

- `critical_prompt.md`
- `context.md` and archived context
- `decisions/ADR-002-two-adoption-modes-one-kernel.md`
- `docs/route-deck-reference.md`
- `docs/agentic-ui-state-runtime.md`
- `docs/using-routedeck.md`
- `architecture/code-map.md`
- core runtime, LangGraph, and examples component docs
- full refactor implementation plan

## Current Reality

RouteDeck has the contract/runtime/store foundation, but lacks the complete
Full Flow compiler, production Core Integration adapter, shared event/SSE
kernel, generated full-stack contract, lightweight Corpus adoption, and the two
required standalone examples.

## Validation

This was a context/architecture planning closeout. No RouteDeck source runtime
was changed or service started.

- RouteDeck documentation coverage advisory: exit `0`; all changed Markdown
  files mapped, with expected context-only anchor warnings.
- SaaStoAgent documentation coverage advisory: exit `0`; no changed source files
  required mapping.
- Dependency-free RouteDeck reference guard: `13` tests passed under Python
  3.12.
- Relative Markdown links: `39` changed/new files checked, `0` missing.
- Scoped `git diff --check`: passed; line-ending conversion notices only.
- Full dependency-backed pytest was not run for this docs-only closeout.

## Next Step

Set and execute the full refactor goal from
`docs/superpowers/plans/2026-07-10-routedeck-full-stack-framework-refactor.md`.
