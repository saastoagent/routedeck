from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from routedeck_core import RouteDeckManifest, validate_manifest


def _masked_payload_keys(data: dict[str, Any]) -> list[str]:
    sensitive = data.get("policies", {}).get("sensitive", {})
    keys = sensitive.get("masked_payload_keys", [])
    return [str(key) for key in keys]


def _module_source(data: dict[str, Any], variable_name: str) -> str:
    manifest_literal = json.dumps(data, indent=2, sort_keys=True)
    masked_literal = json.dumps(_masked_payload_keys(data), indent=2)
    return f'''from __future__ import annotations

from typing import Any

from routedeck_core import RouteDeckManifest, validate_manifest

MANIFEST_DATA: dict[str, Any] = {manifest_literal}

MASKED_PAYLOAD_KEYS: list[str] = {masked_literal}

{variable_name} = RouteDeckManifest.model_validate(MANIFEST_DATA)

MANIFEST_VALIDATION_ERRORS = validate_manifest(
    {variable_name},
    masked_payload_keys=MASKED_PAYLOAD_KEYS,
)


def manifest() -> RouteDeckManifest:
    return {variable_name}


def manifest_json() -> dict[str, Any]:
    return {variable_name}.model_dump(mode="json", by_alias=True)
'''


def scaffold_manifest(input_path: Path, output_path: Path, *, variable_name: str, force: bool) -> list[str]:
    data = json.loads(input_path.read_text(encoding="utf-8"))
    manifest = RouteDeckManifest.model_validate(data)
    errors = validate_manifest(manifest, masked_payload_keys=_masked_payload_keys(data))
    if output_path.exists() and not force:
        raise FileExistsError(f"{output_path} already exists. Use --force to replace it.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_module_source(data, variable_name), encoding="utf-8")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a Python RouteDeck manifest module from JSON.")
    parser.add_argument("input", type=Path, help="Path to a JSON RouteDeck manifest spec.")
    parser.add_argument("output", type=Path, help="Path to write the generated Python module.")
    parser.add_argument("--variable-name", default="MANIFEST", help="Python variable name for the manifest object.")
    parser.add_argument("--force", action="store_true", help="Overwrite the output file if it already exists.")
    args = parser.parse_args()

    errors = scaffold_manifest(
        args.input,
        args.output,
        variable_name=args.variable_name,
        force=args.force,
    )
    if errors:
        print("Generated manifest module with validation errors:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Generated RouteDeck manifest module: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
