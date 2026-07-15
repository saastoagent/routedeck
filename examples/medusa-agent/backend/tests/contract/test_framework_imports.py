from __future__ import annotations

import ast
import inspect
from pathlib import Path


EXPECTED_FRAMEWORK_PACKAGES = (
    "routedeck_core",
    "routedeck_fastapi",
    "routedeck_langgraph",
    "routedeck_sqlalchemy",
)
EXPECTED_PUBLIC_FRAMEWORK_IMPORTS = {
    *EXPECTED_FRAMEWORK_PACKAGES,
    "routedeck_core.app",
    "routedeck_core.contracts.application",
    "routedeck_core.contracts.navigation",
}
FORBIDDEN_PRODUCT_RUNTIME_CONSTRUCTORS = frozenset(
    {
        "RouteDeckOperationRunner",
        "RouteDeckNavigationRunner",
        "RouteDeckDependencies",
        "RouteDeckLangGraphAgentDriver",
    }
)
BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _call_name(function: ast.expr) -> str | None:
    if isinstance(function, ast.Name):
        return function.id
    if isinstance(function, ast.Attribute):
        return function.attr
    return None


def test_medusa_composition_uses_only_public_routedeck_packages() -> None:
    import medusa_agent.composition as composition

    assert composition.framework_packages() == EXPECTED_FRAMEWORK_PACKAGES

    tree = ast.parse(inspect.getsource(composition))
    imported_routedeck_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name.startswith("routedeck_")
    }
    imported_routedeck_modules.update(
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module.startswith("routedeck_")
    )

    assert imported_routedeck_modules == EXPECTED_PUBLIC_FRAMEWORK_IMPORTS


def test_product_backend_does_not_construct_framework_runtime_or_stream_graph() -> None:
    product_paths = tuple(sorted((BACKEND_ROOT / "medusa_agent").rglob("*.py")))
    product_paths = (*product_paths, BACKEND_ROOT / "main.py")
    runtime_constructor_calls: list[str] = []
    stream_calls: list[str] = []
    for path in product_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            call = _call_name(node.func)
            if call in FORBIDDEN_PRODUCT_RUNTIME_CONSTRUCTORS:
                runtime_constructor_calls.append(
                    f"{path.relative_to(BACKEND_ROOT).as_posix()}:{node.lineno}:{call}"
                )
            if call == "astream_events":
                stream_calls.append(
                    f"{path.relative_to(BACKEND_ROOT).as_posix()}:{node.lineno}"
                )

    assert runtime_constructor_calls == []
    assert stream_calls == []


def test_product_main_imports_only_the_public_runtime_router_plane() -> None:
    tree = ast.parse((BACKEND_ROOT / "main.py").read_text(encoding="utf-8"))
    fastapi_imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "routedeck_fastapi"
        for alias in node.names
    }
    internal_route_imports = [
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module.startswith("routedeck_fastapi.routes")
    ]

    assert fastapi_imports == {
        "RouteDeckDependencyUnavailable",
        "SameOriginMutationPolicy",
        "create_routedeck_router_from_runtime_provider",
    }
    assert internal_route_imports == []
