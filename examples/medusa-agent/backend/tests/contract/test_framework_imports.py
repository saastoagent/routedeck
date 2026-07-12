from __future__ import annotations

import ast
import inspect


EXPECTED_FRAMEWORK_PACKAGES = (
    "routedeck_core",
    "routedeck_fastapi",
    "routedeck_langgraph",
    "routedeck_sqlite",
)
EXPECTED_PUBLIC_FRAMEWORK_IMPORTS = {
    *EXPECTED_FRAMEWORK_PACKAGES,
    "routedeck_core.app",
    "routedeck_core.contracts.application",
    "routedeck_core.contracts.navigation",
    "routedeck_core.contracts.operations",
    "routedeck_core.contracts.retention",
    "routedeck_core.navigation",
    "routedeck_core.ports",
    "routedeck_core.state.session",
    "routedeck_core.supervision",
}


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
