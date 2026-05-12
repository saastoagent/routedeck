# Minimal Example

The example in `examples/minimal-fastapi-react` shows the intended framework shape without SaaStoAgent product code.

It demonstrates:

- Backend manifest definition using `routedeck_core`.
- Manifest validation.
- Runtime snapshot generation.
- FastAPI endpoints for manifest, snapshot, and action submission.
- React debugger rendering through `@routedeck/react`.

The example is intentionally small. It does not use LangGraph directly, but the shape mirrors how a LangGraph/FastAPI backend should expose RouteDeck metadata.
