# RouteDeck Manifest Scaffolder

Use this skill when starting a new RouteDeck manifest from a small flow specification.

## Goal

Generate a Python manifest module quickly, then refine it by hand against the real runtime.

## Input Spec

Create a JSON file shaped like `examples/basic-flow.json`:

```json
{
  "version": "example_v1",
  "nodes": [],
  "edges": [],
  "actions": [],
  "policies": {
    "sensitive": {
      "masked_payload_keys": ["password", "token", "api_key"]
    }
  },
  "test_paths": []
}
```

The `nodes`, `edges`, and `actions` entries use the same field names as `RouteDeckManifest`.

## Command

From the RouteDeck folder:

```powershell
python skills/routedeck-manifest-scaffolder/scripts/scaffold_manifest.py skills/routedeck-manifest-scaffolder/examples/basic-flow.json generated_manifest.py --force
```

## Output

The script writes a Python module with:

- `MANIFEST_DATA`
- `MANIFEST`
- `MANIFEST_VALIDATION_ERRORS`
- `manifest()`
- `manifest_json()`

## Follow-Up Steps

1. Move the generated module into the consuming app.
2. Replace placeholder nodes/actions with runtime-backed names.
3. Add app-level action builders for valid actions.
4. Add runtime parity tests.
5. Wire the snapshot into the frontend.

## Limits

The scaffolder does not inspect LangGraph automatically. It creates a starting contract. You still need to verify runtime handlers, action execution, and recovery behavior in the consuming app.
