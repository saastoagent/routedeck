# RouteDeck Architecture

This folder maps RouteDeck architecture to source code, package boundaries, and
validation. Framework narrative docs stay in `docs/`; this folder is for
code-referenced ownership and maintenance.

## Structure

- `code-map.md` - canonical subsystem-to-code/test/doc ownership map
- `components/` - focused component docs for active/high-risk areas

## Current Architecture

RouteDeck is a product-neutral graph-backed state runtime for agentic UI:

```text
Product graph/runtime owns truth.
RouteDeck owns generic manifests, runtime state, projections, operations, surfaces, events, diagnostics, and React store/debugger primitives.
Product adapters translate product state into RouteDeck contracts.
Product UI and product agents consume RouteDeck state and dispatch typed operations.
```

## Source Coverage Rule

Before editing package, example, or test code, check `code-map.md`. During
closeout, name changed source files and either update their architecture/test
anchors or explicitly state why the documented contract is unchanged.

Run `python scripts/check_doc_coverage.py` for an advisory report.
