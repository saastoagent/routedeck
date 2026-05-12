# RouteDeck LangGraph Integration

Use this skill when plugging RouteDeck into a LangGraph-style backend.

## Goal

Wire RouteDeck around the graph so the backend declares current state, valid controls, recovery paths, and diagnostics on every turn.

## Flow Of Control

1. Receive a turn from the client.
   Inputs usually include `user_input`, `selected_action_id`, `action_payload`, and session ID.

2. Resolve persisted runtime state.
   The backend should decide the current executable graph node. Do not trust the client to choose arbitrary nodes.

3. Run the graph or dispatcher.
   Product handlers execute business behavior and produce the next runtime state.

4. Build valid actions for the resulting state.
   These should come from the product adapter and use IDs that exist in the RouteDeck manifest.

5. Build a RouteDeck runtime snapshot.
   Use `build_runtime_snapshot(manifest, current_node=..., valid_actions=..., blocked_actions=..., executed_nodes=..., diagnostics=...)`.

6. Return both the graph response and RouteDeck data.
   The frontend needs the manifest and snapshot to render navigation and debugging.

7. On action click, submit `selected_action_id` back to the backend.
   The backend validates and executes it through the real runtime.

## LangGraph Adapter Pattern

Keep these pieces separate:

- `manifest/catalog`: RouteDeck node, edge, action definitions.
- `runtime handlers`: LangGraph nodes or dispatch handlers.
- `action resolver`: maps selected action IDs to product behavior.
- `snapshot builder`: packages current state and valid actions for the UI.
- `contract tests`: validate manifest and runtime parity.

## Guardrails

- Do not let the React graph mutate runtime state.
- Do not put product-specific logic in `routedeck_core` or `@routedeck/react`.
- Resolve navigation actions before field validation so cancel/back/switch actions never get blocked by stale input validation.
- Empty resume/bootstrap turns should re-prompt or show controls; they should not validate missing user input as an error.
- Mask passwords, tokens, API keys, and credentials in request logs and snapshots.

## Verification

- `validate_manifest(...)` returns no errors.
- Every manifest node has a runtime handler or is explicitly terminal/display-only.
- Every visible action is executable or intentionally disabled with a reason.
- Browser map shows current/reachable/executed state from the backend snapshot.
- Clicking valid action controls sends action IDs to the backend and does not jump nodes locally.
