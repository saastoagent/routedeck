# RouteDeck Architecture

This folder maps RouteDeck architecture to source code, package boundaries, and
validation. Framework narrative docs stay in `docs/`; this folder is for
code-referenced ownership and maintenance.

## Structure

- `feature-coverage.md` - complete capability-to-owner/code/doc/proof matrix
- `code-map.md` - canonical subsystem-to-source/test/doc ownership table
- `documentation-map.md` - canonical versus historical document authority
- `components/` - focused contracts for active/high-risk subsystems

## Current Architecture

RouteDeck is a product-neutral compiled interaction runtime for agentic UI:

```text
Product features own domain truth, declarations, implementations, prompts/graphs, and components.
RouteDeck compiles feature-owned nodes and owns generic session state, supervision, navigation, projection, persistence ports, transport, and browser synchronization.
Product UI and agents consume the same projection and dispatch the same typed operations.
```

## Source Coverage Rule

Before editing package, example, or test code, check `code-map.md`. During
closeout, name changed source files and either update their architecture/test
anchors or explicitly state why the documented contract is unchanged.

Run `python scripts/check_doc_coverage.py` for whole-tree advisory coverage or
pass explicit paths with `--files`. Neither mode invokes Git.
