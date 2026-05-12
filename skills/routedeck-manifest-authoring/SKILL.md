# RouteDeck Manifest Authoring

Use this skill when you need to design or repair a RouteDeck manifest for an agentic workflow.

## Goal

Create a backend-owned RouteDeck manifest that describes user-facing navigation without moving product behavior into the RouteDeck framework.

## Inputs To Gather

- Runtime stage/node names from the real graph or dispatcher.
- User-visible states, not every internal implementation step.
- Actions the user can explicitly choose.
- Free-text inputs accepted at each state.
- Recovery paths such as cancel, back, retry, switch mode, skip, or reopen.
- Sensitive fields and payload keys that must be masked.
- Terminal or handoff states.

## Authoring Steps

1. List concrete runtime stages first.
   Do not invent visible nodes that cannot be mapped back to executable handlers.

2. Decide which stages are visible.
   Keep internal-only graph nodes out of the manifest unless they matter for user recovery or debugging.

3. Write `RouteDeckNodeSpec` entries.
   Each non-terminal node should have at least one of:
   - `allowed_actions`
   - `expected_input`
   - `recovery_prompt`

4. Write `RouteDeckActionSpec` entries.
   Every action should have:
   - stable `id`
   - user-facing `label`
   - `allowed_nodes`
   - `category`
   - `placement`
   - fields when it collects structured input

5. Write `RouteDeckEdgeSpec` entries.
   Edges should represent possible transitions. Use `action_id` when a transition is action-triggered. Use `condition` when the runtime decides based on state or validation.

6. Add policies for sensitive payloads.
   Put secret-like keys in `masked_payload_keys` and mark sensitive fields with `sensitive=True`.

7. Validate the manifest.
   Run `validate_manifest(manifest, masked_payload_keys=...)` and fix every error before wiring it to UI.

8. Add parity checks in the consuming app.
   Confirm manifest nodes map to runtime handlers and visible actions map to executable action handling, unless explicitly display-only.

## Design Rules

- RouteDeck is the navigation contract, not the business runtime.
- Node clicks in the debugger inspect state only.
- User navigation happens by submitting valid RouteDeck action IDs to the backend.
- Do not make arbitrary node jumps executable from the UI.
- Put product copy, auth behavior, workspace behavior, and tool execution in the consuming app.
- Use `parent` only for display grouping. It must not replace concrete runtime nodes.

## Output Checklist

- Manifest module or catalog updated.
- Runtime handler parity checked.
- Action scope checked.
- Snapshot uses real current node and valid actions.
- Sensitive fields are masked.
- Tests cover at least one happy path and one recovery path.
