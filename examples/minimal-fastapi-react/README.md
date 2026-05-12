# Minimal FastAPI + React RouteDeck Example

This example is a compact reference implementation for the framework split.

Backend:

- `backend/app.py` defines a two-node manifest and exposes `/manifest`, `/snapshot`, and `/action`.
- It uses `routedeck_core` only.

Frontend:

- `frontend/src/App.tsx` fetches the manifest/snapshot and renders `RouteDeckDebugger`.
- It uses `@routedeck/react` only.
- The frontend includes a small Tailwind pipeline because the shared debugger uses Tailwind utility classes.

Docker:

```bash
docker compose up -d --build
```

- Frontend: `http://127.0.0.1:5190`
- Backend: `http://127.0.0.1:8096`

This is a framework example, not a SaaStoAgent feature.
