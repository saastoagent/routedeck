from __future__ import annotations

import subprocess
import tempfile
from shutil import which
from pathlib import Path

from scripts.export_contracts import export_runtime_descriptors, export_transport_schema


ROOT = Path(__file__).resolve().parents[1]


def _require_equal(actual: Path, expected: Path) -> None:
    if actual.read_bytes() != expected.read_bytes():
        relative = actual.relative_to(ROOT)
        raise SystemExit(
            f"{relative} is stale; run `pnpm contracts:generate` and check in the result"
        )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="routedeck-contracts-") as temporary:
        output = Path(temporary)
        schema = export_transport_schema(output / "routedeck.schema.json")
        runtime = export_runtime_descriptors(output / "generatedRuntime.ts")
        generated = output / "generated.ts"
        pnpm = which("pnpm") or which("pnpm.cmd")
        if pnpm is None:
            raise SystemExit("pnpm is required to check generated TypeScript contracts")
        subprocess.run(
            [
                pnpm,
                "exec",
                "json2ts",
                "-i",
                str(schema),
                "-o",
                str(generated),
            ],
            cwd=ROOT,
            check=True,
        )
        _require_equal(
            ROOT / "packages/core/schema/routedeck.schema.json",
            schema,
        )
        _require_equal(
            ROOT / "packages/core/src/contracts/generatedRuntime.ts",
            runtime,
        )
        _require_equal(
            ROOT / "packages/core/src/contracts/generated.ts",
            generated,
        )
    print("Generated RouteDeck contracts are current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
