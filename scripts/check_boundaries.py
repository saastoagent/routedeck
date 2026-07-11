from __future__ import annotations

import argparse
import ast
import json
from collections.abc import Sequence
from pathlib import Path


CORE_FORBIDDEN_IMPORTS = (
    "fastapi",
    "langgraph",
    "langchain",
    "httpx",
    "sqlite3",
    "medusa_agent",
    "routedeck_fastapi",
    "routedeck_langgraph",
    "routedeck_sqlite",
)
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _is_forbidden(module: str, forbidden: Sequence[str]) -> bool:
    return any(
        module == forbidden_module or module.startswith(f"{forbidden_module}.")
        for forbidden_module in forbidden
    )


def _display_path(path: Path, package_path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return resolved.relative_to(package_path.parent).as_posix()


def scan_python_imports(
    package: str | Path,
    forbidden: Sequence[str],
) -> list[str]:
    requested_path = Path(package)
    package_path = (
        requested_path.resolve()
        if requested_path.is_absolute()
        else (PROJECT_ROOT / requested_path).resolve()
    )
    if not package_path.is_dir():
        raise FileNotFoundError(f"Python package directory does not exist: {package_path}")

    violations: list[tuple[str, int, str]] = []
    for path in sorted(package_path.rglob("*.py"), key=lambda item: item.as_posix()):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        display_path = _display_path(path, package_path)
        for node in ast.walk(tree):
            imported_modules: tuple[str, ...]
            if isinstance(node, ast.Import):
                imported_modules = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported_modules = (node.module,)
            else:
                continue

            for module in imported_modules:
                if _is_forbidden(module, forbidden):
                    violations.append((display_path, node.lineno, module))

    return [
        f"{path}:{line}:{module}"
        for path, line, module in sorted(violations)
    ]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check RouteDeck Python dependency boundaries."
    )
    parser.add_argument("--json", required=True, type=Path, dest="json_path")
    args = parser.parse_args(argv)

    violations = scan_python_imports(
        package="routedeck_core",
        forbidden=CORE_FORBIDDEN_IMPORTS,
    )
    report = {
        "schema_version": 1,
        "status": "pass" if not violations else "fail",
        "violation_count": len(violations),
        "checks": [
            {
                "name": "core_imports",
                "package": "routedeck_core",
                "forbidden_modules": list(CORE_FORBIDDEN_IMPORTS),
                "violations": violations,
            }
        ],
    }
    args.json_path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    args.json_path.write_text(f"{rendered}\n", encoding="utf-8")
    print(rendered)
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
