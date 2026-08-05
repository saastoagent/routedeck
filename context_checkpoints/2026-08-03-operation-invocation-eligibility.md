# Operation invocation eligibility checkpoint

Date: 2026-08-03

RouteDeck now distinguishes node legality from invocation-source eligibility.
Every Operation requires explicit allowed sources; compiler, projection,
LangGraph model context, the supervised runner, generated contracts, strict
headless decoders, and RouteDeck-owned declarations are aligned.

The change is verified and staged but intentionally uncommitted. Corpus and
Design Studio adoption is the next separate consumer slice. Exact validation,
known unrelated stale assertions, and ownership are recorded in
`logs/20260803_operation_invocation_eligibility.md`.
