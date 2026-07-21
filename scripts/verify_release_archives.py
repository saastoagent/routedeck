from __future__ import annotations

import argparse
import json
import tarfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Iterable


class ArchiveVerificationError(RuntimeError):
    """Raised when a release archive does not match its public contract."""


PYTHON_PACKAGES = (
    "routedeck_core",
    "routedeck_fastapi",
    "routedeck_langgraph",
    "routedeck_sqlalchemy",
    "routedeck_testing",
)


def _normalized(names: Iterable[str]) -> tuple[str, ...]:
    return tuple(
        str(PurePosixPath(name.replace("\\", "/")))
        for name in names
        if name and not name.endswith("/")
    )


def _reject(names: tuple[str, ...], forbidden: tuple[str, ...]) -> None:
    violations = sorted(
        name
        for name in names
        if any(fragment in name.lower() for fragment in forbidden)
    )
    if violations:
        raise ArchiveVerificationError(
            "archive contains forbidden paths: " + ", ".join(violations)
        )


def verify_python_wheel(path: Path) -> dict[str, object]:
    if not path.is_file() or path.suffix != ".whl":
        raise ArchiveVerificationError(f"Python wheel does not exist: {path}")
    with zipfile.ZipFile(path) as archive:
        names = _normalized(archive.namelist())

    _reject(
        names,
        (
            "/tests/",
            "tests/",
            "examples/",
            "__pycache__",
            ".pyc",
            ".pyo",
            ".env",
            ".sqlite",
            "node_modules/",
            "artifacts/",
        ),
    )
    missing = [
        package for package in PYTHON_PACKAGES if f"{package}/__init__.py" not in names
    ]
    if missing:
        raise ArchiveVerificationError(
            "wheel is missing advertised packages: " + ", ".join(missing)
        )
    if not any(name.endswith(".dist-info/METADATA") for name in names):
        raise ArchiveVerificationError("wheel is missing distribution metadata")
    return {"archive": str(path), "kind": "python-wheel", "file_count": len(names)}


def verify_npm_archive(path: Path) -> dict[str, object]:
    if not path.is_file() or not path.name.endswith(".tgz"):
        raise ArchiveVerificationError(f"npm archive does not exist: {path}")
    with tarfile.open(path, "r:gz") as archive:
        names = _normalized(
            member.name for member in archive.getmembers() if member.isfile()
        )

    _reject(
        names,
        (
            ".test.",
            ".spec.",
            ".tsbuildinfo",
            "node_modules/",
            "package/src/",
            "__pycache__",
            ".env",
            ".sqlite",
            "artifacts/",
        ),
    )
    required = {
        "package/package.json",
        "package/README.md",
        "package/LICENSE",
        "package/dist/index.js",
        "package/dist/index.d.ts",
    }
    missing = sorted(required.difference(names))
    if missing:
        raise ArchiveVerificationError(
            "npm archive is missing required files: " + ", ".join(missing)
        )
    return {"archive": str(path), "kind": "npm", "file_count": len(names)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify RouteDeck release archives")
    parser.add_argument("--python-wheel", type=Path)
    parser.add_argument("--npm", action="append", type=Path, default=[])
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    if args.python_wheel is None and not args.npm:
        parser.error("at least one --python-wheel or --npm archive is required")

    results: list[dict[str, object]] = []
    if args.python_wheel is not None:
        results.append(verify_python_wheel(args.python_wheel))
    results.extend(verify_npm_archive(path) for path in args.npm)
    payload = {"status": "pass", "archives": results}
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
