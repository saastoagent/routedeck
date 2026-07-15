from __future__ import annotations

import ast
from pathlib import Path

import pytest


CORE_FORBIDDEN_IMPORTS = (
    "fastapi",
    "langgraph",
    "langchain",
    "httpx",
    "sqlite3",
    "medusa_agent",
    "routedeck_fastapi",
    "routedeck_langgraph",
    "routedeck_sqlalchemy",
    "sqlalchemy",
    "psycopg",
)


def test_core_has_no_adapter_or_product_imports() -> None:
    from scripts.check_boundaries import scan_python_imports

    violations = scan_python_imports(
        package="routedeck_core",
        forbidden=CORE_FORBIDDEN_IMPORTS,
    )

    assert violations == []


def test_import_scan_uses_ast_exact_and_dotted_module_matching(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from scripts.check_boundaries import scan_python_imports

    package = tmp_path / "sample_package"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "imports.py").write_text(
        "\n".join(
            (
                "# import fastapi",
                'DOCUMENTATION = "from httpx import Client"',
                "import fastapi_tools",
                "import fastapi",
                "import fastapi.routing as routing",
                "import safe_module, httpx._client",
                "from langgraph.graph import StateGraph",
                "from sqlite3 import connect",
                "from . import local_module",
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    violations = scan_python_imports(
        package=package,
        forbidden=("fastapi", "httpx", "langgraph", "sqlite3"),
    )

    assert violations == [
        "sample_package/imports.py:4:fastapi",
        "sample_package/imports.py:5:fastapi.routing",
        "sample_package/imports.py:6:httpx._client",
        "sample_package/imports.py:7:langgraph.graph",
        "sample_package/imports.py:8:sqlite3",
    ]


def test_import_scan_resolves_project_packages_outside_caller_working_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from scripts.check_boundaries import scan_python_imports

    monkeypatch.chdir(tmp_path)

    assert (
        scan_python_imports(
            package="routedeck_core",
            forbidden=CORE_FORBIDDEN_IMPORTS,
        )
        == []
    )


def test_import_scan_fails_loudly_for_missing_package() -> None:
    from scripts.check_boundaries import scan_python_imports

    with pytest.raises(
        FileNotFoundError, match="Python package directory does not exist"
    ):
        scan_python_imports(
            package="missing_routedeck_package",
            forbidden=CORE_FORBIDDEN_IMPORTS,
        )


def test_runtime_ownership_proof_uses_ast_constructor_and_identity_flow() -> None:
    from scripts.check_boundaries import (
        _assigned_constructor_calls,
        _keyword_expression,
        _tree_attribute_chains,
    )

    tree = ast.parse(
        "\n".join(
            (
                '# RouteDeckOperationRunner(operation_runner="not code")',
                'DOCUMENTATION = "dependencies.runner.dispatch"',
                "runner = RouteDeckOperationRunner(app=app)",
                "navigation = RouteDeckNavigationRunner(operation_runner=runner)",
                "result = dependencies.runner.dispatch(request)",
            )
        )
    )

    runner_calls = _assigned_constructor_calls(tree, "RouteDeckOperationRunner")
    navigation_calls = _assigned_constructor_calls(
        tree, "RouteDeckNavigationRunner"
    )

    assert len(runner_calls) == 1
    assert runner_calls[0][1] == "runner"
    assert len(navigation_calls) == 1
    assert navigation_calls[0][1] == "navigation"
    assert _keyword_expression(navigation_calls[0][2], "operation_runner") == "runner"
    assert "dependencies.runner.dispatch" in _tree_attribute_chains(tree)
