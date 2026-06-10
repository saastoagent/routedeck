# Minimal Example

Product-neutral minimal examples are currently deferred. The active visible
adoption example is `examples/medusa-agent`, and it must remain a Medusa Agent
product example rather than being replaced by a RouteDeck dashboard or generic
demo.

The previous attempted examples at `examples/minimal-langgraph-adapter` and
`examples/minimal-fastapi-react` were removed during the 2026-06-09 Medusa
recalibration because they created the wrong visible slice. Do not recreate
them as part of Medusa Agent work unless the user explicitly asks for a separate
product-neutral framework example.

## Current Example Policy

- Medusa Agent is the active product reference example.
- RouteDeck framework packages stay product-neutral.
- Generic examples may return later, but only as framework docs/examples, not as
  substitutes for a requested Medusa visible slice.
- Any future generic example must have its own plan, tests, and acceptance
  criteria separate from Medusa Agent.

## Current Validation

```powershell
cd examples/medusa-agent/backend
python -m pytest tests -q
```

```powershell
cd examples/medusa-agent/frontend
npm test
```
