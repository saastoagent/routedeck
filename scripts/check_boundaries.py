from __future__ import annotations

import argparse
import ast
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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
REQUIRED_CHECK_NAMES = (
    "core_imports",
    "store_endpoint_inventory",
    "handler_client_port",
    "browser_network",
    "product_transport_separation",
    "runtime_ownership",
    "source_policy_scan",
    "architectural_review",
)
BOUNDARY_REPORT_SCHEMA_VERSION = 4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = Path("routedeck_core")
FRAMEWORK_PYTHON_ROOTS = (
    CORE_ROOT,
    Path("routedeck_fastapi"),
    Path("routedeck_langgraph"),
    Path("routedeck_sqlalchemy"),
)
PRODUCT_BACKEND_ROOT = Path("examples/medusa-agent/backend/medusa_agent")
PRODUCT_MAIN = Path("examples/medusa-agent/backend/main.py")
FEATURE_ROOT = PRODUCT_BACKEND_ROOT / "features"
HTTP_ADAPTER = PRODUCT_BACKEND_ROOT / "medusa/client/http.py"
HTTP_TRANSPORT = PRODUCT_BACKEND_ROOT / "medusa/client/transport.py"
MEDUSA_RESOURCE_ROOT = PRODUCT_BACKEND_ROOT / "medusa/client/resources"
STORE_RESOURCE_OWNERS = (
    MEDUSA_RESOURCE_ROOT / "catalog.py",
    MEDUSA_RESOURCE_ROOT / "cart.py",
    MEDUSA_RESOURCE_ROOT / "checkout.py",
    MEDUSA_RESOURCE_ROOT / "orders.py",
)
STORE_ENDPOINT_OWNERS = (*STORE_RESOURCE_OWNERS, HTTP_TRANSPORT)
HTTP_CLIENT_OWNERS = (
    HTTP_ADAPTER,
    HTTP_TRANSPORT,
    MEDUSA_RESOURCE_ROOT / "base.py",
)
CLIENT_PROTOCOL = PRODUCT_BACKEND_ROOT / "medusa/client/protocol.py"
PRODUCT_API_ROOT = PRODUCT_BACKEND_ROOT / "api"
CORE_RUNTIME = CORE_ROOT / "runtime.py"
FASTAPI_RUNTIME = Path("routedeck_fastapi/runtime.py")
FASTAPI_ROUTER = Path("routedeck_fastapi/router.py")
FASTAPI_ROUTES_ROOT = Path("routedeck_fastapi/routes")
REQUIRED_FASTAPI_ROUTE_MODULES = frozenset(
    {
        "__init__.py",
        "contract.py",
        "sessions.py",
        "operations.py",
        "conversation.py",
        "events.py",
        "private_forms.py",
        "inspection.py",
    }
)
FORBIDDEN_PRODUCT_RUNTIME_CONSTRUCTORS = frozenset(
    {
        "RouteDeckOperationRunner",
        "RouteDeckNavigationRunner",
        "RouteDeckDependencies",
        "RouteDeckLangGraphAgentDriver",
    }
)
FRONTEND_SOURCE_ROOT = Path("examples/medusa-agent/frontend/src")
FRAMEWORK_TYPESCRIPT_ROOTS = (
    Path("packages/core/src"),
    Path("packages/react/src"),
)
MEDUSA_SERVER_ROOT = Path("examples/medusa-agent/medusa")
MEDUSA_COMPOSE = Path("examples/medusa-agent/infra/compose.yaml")
MEDUSA_COMPOSE_CONTEXT = "../medusa"
MEDUSA_PACKAGE_MANAGER = "npm@10.8.2"
MEDUSA_DOCKER_BASE = (
    "node:20.19.4-bookworm-slim@"
    "sha256:6db5e436948af8f0244488a1f658c2c8e55a3ae51ca2e1686ed042be8f25f70a"
)
MEDUSA_PINNED_RUNTIME_DEPENDENCIES = {
    "@medusajs/admin-sdk": "2.13.6",
    "@medusajs/cli": "2.13.6",
    "@medusajs/framework": "2.13.6",
    "@medusajs/medusa": "2.13.6",
    "pg": "8.16.3",
}
MEDUSA_REQUIRED_SOURCE_FILES = (
    Path(".dockerignore"),
    Path("Dockerfile"),
    Path("README.md"),
    Path("medusa-config.ts"),
    Path("package-lock.json"),
    Path("package.json"),
    Path("start.sh"),
    Path("tsconfig.json"),
    Path("src/scripts/seed.ts"),
)

HTTP_CLIENT_MODULES = ("httpx", "requests", "aiohttp", "urllib.request")
FRONTEND_MEDUSA_SDK_PREFIXES = ("@medusajs/", "medusa-js")
FRONTEND_FORBIDDEN_NETWORK_FRAGMENTS = (
    "/store/",
    "http://127.0.0.1:9100",
    "http://localhost:9100",
    "https://127.0.0.1:9100",
    "https://localhost:9100",
)
PRODUCTION_TEST_MODULES = (
    "pytest",
    "unittest.mock",
    "faker",
    "routedeck_testing",
    "tests",
)
FORBIDDEN_POLICY_SYMBOLS = (
    "keyword_router",
    "phrase_router",
    "intent_router",
    "keyword_map",
    "phrase_map",
    "intent_map",
    "canned_response",
    "fallback_response",
    "mock_catalog",
    "fixture_catalog",
    "sample_catalog",
)
TOPOLOGY_MUTATORS = (
    "add_node",
    "add_edge",
    "set_entry_point",
    "set_finish_point",
    "compile",
)
ASSISTANT_STREAM_EVENT_DISCRIMINANTS = frozenset(
    {
        "stream_start",
        "conversation_snapshot",
        "assistant_delta",
        "assistant_reset",
        "assistant_end",
        "review_required",
        "chat_error",
        "stream_end",
    }
)
FORBIDDEN_FRAMEWORK_PRODUCT_VOCABULARY = re.compile(
    r"\bbuyer(?:-agent)?\b",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class BoundaryCheck:
    name: str
    evidence: Mapping[str, Any]
    violations: tuple[str, ...]

    @property
    def status(self) -> str:
        return "pass" if not self.violations else "fail"

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "evidence": dict(self.evidence),
            "violations": list(self.violations),
        }


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


def _project_path(project_root: Path, relative: Path, *, kind: str) -> Path:
    path = (project_root / relative).resolve()
    exists = path.is_dir() if kind == "directory" else path.is_file()
    if not exists:
        raise FileNotFoundError(f"Required production root is missing: {path}")
    return path


def _relative(path: Path, project_root: Path) -> str:
    return path.resolve().relative_to(project_root.resolve()).as_posix()


def _python_files(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(root.rglob("*.py"), key=lambda path: path.as_posix()))


def _parse_python(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imported_modules(tree: ast.AST) -> tuple[tuple[int, str], ...]:
    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append((node.lineno, node.module))
    return tuple(sorted(imports))


def _string_literals(tree: ast.AST) -> tuple[tuple[int, str], ...]:
    values = {
        (node.lineno, node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    return tuple(sorted(values))


def _call_name(function: ast.expr) -> str | None:
    if isinstance(function, ast.Name):
        return function.id
    if isinstance(function, ast.Attribute):
        return function.attr
    return None


def _attribute_chain(value: ast.AST) -> str | None:
    if isinstance(value, ast.Name):
        return value.id
    if isinstance(value, ast.Attribute):
        prefix = _attribute_chain(value.value)
        return f"{prefix}.{value.attr}" if prefix else value.attr
    return None


def _production_python_files(project_root: Path) -> tuple[Path, ...]:
    files: list[Path] = []
    for relative in (*FRAMEWORK_PYTHON_ROOTS, PRODUCT_BACKEND_ROOT):
        files.extend(
            _python_files(_project_path(project_root, relative, kind="directory"))
        )
    files.append(_project_path(project_root, PRODUCT_MAIN, kind="file"))
    return tuple(sorted(set(files), key=lambda path: path.as_posix()))


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
        raise FileNotFoundError(
            f"Python package directory does not exist: {package_path}"
        )

    violations: list[tuple[str, int, str]] = []
    for path in _python_files(package_path):
        tree = _parse_python(path)
        display_path = _display_path(path, package_path)
        for line, module in _imported_modules(tree):
            if _is_forbidden(module, forbidden):
                violations.append((display_path, line, module))

    return [f"{path}:{line}:{module}" for path, line, module in sorted(violations)]


def check_core_imports(project_root: Path = PROJECT_ROOT) -> BoundaryCheck:
    core = _project_path(project_root, CORE_ROOT, kind="directory")
    violations = scan_python_imports(core, CORE_FORBIDDEN_IMPORTS)
    return BoundaryCheck(
        name="core_imports",
        evidence={
            "package": CORE_ROOT.as_posix(),
            "scanned_file_count": len(_python_files(core)),
            "forbidden_modules": list(CORE_FORBIDDEN_IMPORTS),
        },
        violations=tuple(violations),
    )


def _is_store_path(value: str) -> bool:
    return value == "/store" or value.startswith("/store/")


def check_store_endpoint_inventory(
    project_root: Path = PROJECT_ROOT,
) -> BoundaryCheck:
    endpoint_owners = {
        _project_path(project_root, relative, kind="file")
        for relative in STORE_ENDPOINT_OWNERS
    }
    required_resource_owners = {
        _project_path(project_root, relative, kind="file")
        for relative in STORE_RESOURCE_OWNERS
    }
    transport_owners = {
        _project_path(project_root, relative, kind="file")
        for relative in HTTP_CLIENT_OWNERS
    }
    endpoints: list[dict[str, Any]] = []
    transports: list[dict[str, Any]] = []
    violations: list[str] = []
    for path in _production_python_files(project_root):
        tree = _parse_python(path)
        display = _relative(path, project_root)
        for line, value in _string_literals(tree):
            if not _is_store_path(value):
                continue
            endpoints.append({"path": display, "line": line, "template": value})
            if path not in endpoint_owners:
                violations.append(
                    f"{display}:{line}:Store endpoint literal outside the resource/transport owner inventory"
                )
        for line, module in _imported_modules(tree):
            if not _is_forbidden(module, HTTP_CLIENT_MODULES):
                continue
            transports.append({"path": display, "line": line, "module": module})
            if path not in transport_owners:
                violations.append(
                    f"{display}:{line}:HTTP client import outside the explicit Medusa transport owner inventory:{module}"
                )
    endpoint_paths = {item["path"] for item in endpoints}
    for owner in sorted(required_resource_owners, key=lambda path: path.as_posix()):
        display = _relative(owner, project_root)
        if display not in endpoint_paths:
            violations.append(f"{display}:no Store endpoint templates found")
    transport_display = HTTP_TRANSPORT.as_posix()
    if not any(item["path"] == transport_display for item in transports):
        violations.append(f"{transport_display}:no HTTP transport import found")
    return BoundaryCheck(
        name="store_endpoint_inventory",
        evidence={
            "endpoint_owners": sorted(
                _relative(path, project_root) for path in endpoint_owners
            ),
            "required_resource_owners": sorted(
                _relative(path, project_root) for path in required_resource_owners
            ),
            "transport_modules": sorted(
                _relative(path, project_root) for path in transport_owners
            ),
            "scanned_file_count": len(_production_python_files(project_root)),
            "endpoint_templates": endpoints,
            "http_transports": transports,
        },
        violations=tuple(sorted(violations)),
    )


def _class_protocol_methods(tree: ast.Module, class_name: str) -> frozenset[str]:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return frozenset(
                child.name
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                and not child.name.startswith("_")
            )
    return frozenset()


def check_handler_client_port(project_root: Path = PROJECT_ROOT) -> BoundaryCheck:
    protocol_path = _project_path(project_root, CLIENT_PROTOCOL, kind="file")
    feature_root = _project_path(project_root, FEATURE_ROOT, kind="directory")
    protocol_methods = _class_protocol_methods(
        _parse_python(protocol_path), "MedusaStoreClient"
    )
    violations: list[str] = []
    call_sites: list[dict[str, Any]] = []
    typed_consumer_files: set[str] = set()
    if not protocol_methods:
        violations.append(
            f"{CLIENT_PROTOCOL.as_posix()}:MedusaStoreClient has no methods"
        )

    for path in _python_files(feature_root):
        tree = _parse_python(path)
        display = _relative(path, project_root)
        imports = _imported_modules(tree)
        for line, module in imports:
            if _is_forbidden(module, HTTP_CLIENT_MODULES) or module.endswith(
                "medusa.client.http"
            ):
                violations.append(
                    f"{display}:{line}:feature imports concrete HTTP client:{module}"
                )
        has_port_reference = any(
            isinstance(node, ast.Name) and node.id == "MedusaStoreClient"
            for node in ast.walk(tree)
        )
        file_calls: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(
                node.func, ast.Attribute
            ):
                continue
            if node.func.attr not in protocol_methods:
                continue
            receiver = _attribute_chain(node.func.value)
            if receiver not in {"client", "self.client"}:
                continue
            file_calls.append(
                {"line": node.lineno, "method": node.func.attr, "receiver": receiver}
            )
        if file_calls:
            call_sites.append({"path": display, "calls": file_calls})
            if has_port_reference:
                typed_consumer_files.add(display)
            else:
                violations.append(
                    f"{display}:Medusa client calls lack MedusaStoreClient port annotation"
                )
    if not call_sites:
        violations.append(
            f"{FEATURE_ROOT.as_posix()}:no MedusaStoreClient call sites found"
        )
    return BoundaryCheck(
        name="handler_client_port",
        evidence={
            "protocol": CLIENT_PROTOCOL.as_posix(),
            "protocol_methods": sorted(protocol_methods),
            "client_call_sites": call_sites,
            "typed_consumer_files": sorted(typed_consumer_files),
        },
        violations=tuple(sorted(violations)),
    )


def _typescript_production_files(root: Path) -> tuple[Path, ...]:
    return tuple(
        path
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix())
        if path.is_file()
        and path.suffix in {".ts", ".tsx"}
        and "tests" not in path.relative_to(root).parts
        and ".test." not in path.name
        and path.name != "generated.ts"
    )


def _typescript_code_mask(text: str) -> str:
    """Mask comments and literals while preserving source positions/newlines."""

    masked = list(text)
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        next_char = text[index + 1] if index + 1 < length else ""
        if char == "/" and next_char == "/":
            masked[index] = masked[index + 1] = " "
            index += 2
            while index < length and text[index] != "\n":
                masked[index] = " "
                index += 1
            continue
        if char == "/" and next_char == "*":
            masked[index] = masked[index + 1] = " "
            index += 2
            while index < length:
                if text[index] == "*" and index + 1 < length and text[index + 1] == "/":
                    masked[index] = masked[index + 1] = " "
                    index += 2
                    break
                if text[index] != "\n":
                    masked[index] = " "
                index += 1
            continue
        if char not in {'"', "'", "`"}:
            index += 1
            continue
        quote = char
        masked[index] = " "
        index += 1
        while index < length:
            char = text[index]
            if char == "\\" and index + 1 < length:
                masked[index] = " "
                if text[index + 1] != "\n":
                    masked[index + 1] = " "
                index += 2
                continue
            if char == quote:
                masked[index] = " "
                index += 1
                break
            if char != "\n":
                masked[index] = " "
            index += 1
    return "".join(masked)


def _typescript_string_literals(text: str) -> tuple[tuple[int, str], ...]:
    literals: list[tuple[int, str]] = []
    index = 0
    line = 1
    length = len(text)
    while index < length:
        char = text[index]
        next_char = text[index + 1] if index + 1 < length else ""
        if char == "\n":
            line += 1
            index += 1
            continue
        if char == "/" and next_char == "/":
            index += 2
            while index < length and text[index] != "\n":
                index += 1
            continue
        if char == "/" and next_char == "*":
            index += 2
            while index < length:
                if text[index] == "\n":
                    line += 1
                if text[index] == "*" and index + 1 < length and text[index + 1] == "/":
                    index += 2
                    break
                index += 1
            continue
        if char not in {'"', "'", "`"}:
            index += 1
            continue
        quote = char
        start_line = line
        value: list[str] = []
        index += 1
        while index < length:
            char = text[index]
            if char == "\\" and index + 1 < length:
                value.append(text[index + 1])
                index += 2
                continue
            if char == quote:
                index += 1
                break
            if char == "\n":
                line += 1
            value.append(char)
            index += 1
        literals.append((start_line, "".join(value)))
    return tuple(literals)


def check_browser_network(project_root: Path = PROJECT_ROOT) -> BoundaryCheck:
    source_root = _project_path(project_root, FRONTEND_SOURCE_ROOT, kind="directory")
    violations: list[str] = []
    inspected_literal_count = 0
    files = _typescript_production_files(source_root)
    for path in files:
        display = _relative(path, project_root)
        for line, value in _typescript_string_literals(
            path.read_text(encoding="utf-8")
        ):
            inspected_literal_count += 1
            reasons = [
                fragment
                for fragment in FRONTEND_FORBIDDEN_NETWORK_FRAGMENTS
                if fragment in value
            ]
            reasons.extend(
                prefix
                for prefix in FRONTEND_MEDUSA_SDK_PREFIXES
                if value == prefix or value.startswith(prefix)
            )
            if reasons:
                violations.append(
                    f"{display}:{line}:forbidden browser network dependency:{','.join(sorted(set(reasons)))}"
                )
    return BoundaryCheck(
        name="browser_network",
        evidence={
            "production_root": FRONTEND_SOURCE_ROOT.as_posix(),
            "scanned_files": [_relative(path, project_root) for path in files],
            "inspected_string_literal_count": inspected_literal_count,
            "forbidden_network_fragments": list(FRONTEND_FORBIDDEN_NETWORK_FRAGMENTS),
            "forbidden_sdk_prefixes": list(FRONTEND_MEDUSA_SDK_PREFIXES),
            "proof_scope": (
                "Static production-source proof only; captured runtime traffic is a "
                "separate mandatory Playwright release artifact."
            ),
        },
        violations=tuple(sorted(violations)),
    )


def _router_inventory(path: Path, project_root: Path) -> dict[str, Any]:
    tree = _parse_python(path)
    prefixes: list[dict[str, Any]] = []
    endpoints: list[dict[str, Any]] = []
    verbs = {"get", "post", "put", "patch", "delete"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _call_name(node.func) == "APIRouter":
            prefix = next(
                (
                    keyword.value.value
                    for keyword in node.keywords
                    if keyword.arg == "prefix"
                    and isinstance(keyword.value, ast.Constant)
                    and isinstance(keyword.value.value, str)
                ),
                None,
            )
            prefixes.append({"line": node.lineno, "prefix": prefix})
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr in verbs
                and decorator.args
                and isinstance(decorator.args[0], ast.Constant)
                and isinstance(decorator.args[0].value, str)
            ):
                endpoints.append(
                    {
                        "line": decorator.lineno,
                        "verb": decorator.func.attr.upper(),
                        "path": decorator.args[0].value,
                    }
                )
    return {
        "path": _relative(path, project_root),
        "prefixes": prefixes,
        "endpoints": endpoints,
    }


def _included_router_factory_calls(tree: ast.AST) -> tuple[str, ...]:
    factories: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or _call_name(node.func) != "include_router":
            continue
        if not node.args:
            continue
        argument = node.args[0]
        if isinstance(argument, ast.Call):
            name = _call_name(argument.func)
        else:
            name = _call_name(argument) if isinstance(argument, ast.expr) else None
        if name:
            factories.append(name)
    return tuple(factories)


def _included_router_factories(tree: ast.AST) -> frozenset[str]:
    return frozenset(_included_router_factory_calls(tree))


def check_product_transport_separation(
    project_root: Path = PROJECT_ROOT,
) -> BoundaryCheck:
    generic_router_path = _project_path(
        project_root, FASTAPI_ROUTER, kind="file"
    )
    routes_root = _project_path(
        project_root, FASTAPI_ROUTES_ROOT, kind="directory"
    )
    route_module_paths = _python_files(routes_root)
    route_module_names = frozenset(path.name for path in route_module_paths)
    generic_paths = (generic_router_path, *route_module_paths)
    api_root = _project_path(project_root, PRODUCT_API_ROOT, kind="directory")
    main_path = _project_path(project_root, PRODUCT_MAIN, kind="file")
    generic = [_router_inventory(path, project_root) for path in generic_paths]
    product_paths = tuple(
        path for path in _python_files(api_root) if path.name != "__init__.py"
    )
    product = [_router_inventory(path, project_root) for path in product_paths]
    violations: list[str] = []
    if route_module_names != REQUIRED_FASTAPI_ROUTE_MODULES:
        missing = sorted(REQUIRED_FASTAPI_ROUTE_MODULES.difference(route_module_names))
        extra = sorted(route_module_names.difference(REQUIRED_FASTAPI_ROUTE_MODULES))
        violations.append(
            f"{FASTAPI_ROUTES_ROOT.as_posix()}:route module inventory drifted:"
            f"missing={missing!r}:extra={extra!r}"
        )
    generic_prefixes = {
        item["prefix"]
        for inventory in generic
        for item in inventory["prefixes"]
        if item["prefix"] is not None
    }
    if generic_prefixes != {"/api/routedeck"}:
        violations.append(
            f"{FASTAPI_ROUTER.as_posix()}:generic router prefix must be exactly /api/routedeck"
        )
    for generic_path in generic_paths:
        generic_tree = _parse_python(generic_path)
        for line, module in _imported_modules(generic_tree):
            if _is_forbidden(module, ("medusa_agent",)):
                violations.append(
                    f"{_relative(generic_path, project_root)}:{line}:generic router imports product:{module}"
                )
        for line, value in _string_literals(generic_tree):
            if value.startswith("/api/medusa-agent") or _is_store_path(value):
                violations.append(
                    f"{_relative(generic_path, project_root)}:{line}:product path in generic router:{value}"
                )
    product_prefixes = {
        item["prefix"]
        for inventory in product
        for item in inventory["prefixes"]
        if item["prefix"] is not None
    }
    if not product_prefixes or product_prefixes != {"/api/medusa-agent"}:
        violations.append(
            f"{PRODUCT_API_ROOT.as_posix()}:product health router must use /api/medusa-agent"
        )
    product_route_files = {
        _relative(path, project_root) for path in product_paths
    }
    expected_product_route_files = {
        (PRODUCT_API_ROOT / "health.py").as_posix()
    }
    if product_route_files != expected_product_route_files:
        violations.append(
            f"{PRODUCT_API_ROOT.as_posix()}:only product health transport is allowed:"
            f"found={sorted(product_route_files)!r}"
        )
    for inventory in product:
        path = project_root / inventory["path"]
        for line, value in _string_literals(_parse_python(path)):
            if value.startswith("/api/routedeck") or _is_store_path(value):
                violations.append(
                    f"{inventory['path']}:{line}:framework/Store path in product API:{value}"
                )
    included_calls = _included_router_factory_calls(_parse_python(main_path))
    included = frozenset(included_calls)
    required_includes = {
        "create_routedeck_router_from_runtime_provider",
        "health_router",
    }
    if included != required_includes or len(included_calls) != len(required_includes):
        violations.append(
            f"{PRODUCT_MAIN.as_posix()}:router composition must contain only the generic "
            f"runtime router and product health:found={sorted(included)!r}"
        )
    return BoundaryCheck(
        name="product_transport_separation",
        evidence={
            "required_generic_route_modules": sorted(
                REQUIRED_FASTAPI_ROUTE_MODULES
            ),
            "generic_route_module_inventory": sorted(route_module_names),
            "generic_routers": generic,
            "product_routers": product,
            "application_router_includes": sorted(included),
            "application_router_include_calls": list(included_calls),
        },
        violations=tuple(sorted(violations)),
    )


def _assigned_constructor_calls(
    tree: ast.AST, constructor: str
) -> tuple[tuple[int, str | None, ast.Call], ...]:
    calls: list[tuple[int, str | None, ast.Call]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if not isinstance(value, ast.Call) or _call_name(value.func) != constructor:
            continue
        target: ast.expr | None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
        elif isinstance(node, ast.AnnAssign):
            target = node.target
        else:
            target = None
        calls.append((node.lineno, _attribute_chain(target) if target else None, value))
    return tuple(calls)


def _keyword_expression(call: ast.Call, name: str) -> str | None:
    for keyword in call.keywords:
        if keyword.arg == name:
            return ast.unparse(keyword.value)
    return None


def _tree_attribute_chains(tree: ast.AST) -> frozenset[str]:
    return frozenset(
        chain
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and (chain := _attribute_chain(node)) is not None
    )


def _constructor_calls(tree: ast.AST, constructor: str) -> tuple[ast.Call, ...]:
    return tuple(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _call_name(node.func) == constructor
    )


def _function_definition(
    tree: ast.Module,
    name: str,
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    return next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == name
        ),
        None,
    )


def _dependency_chains(
    project_root: Path,
    paths: Sequence[Path],
) -> tuple[list[str], frozenset[str]]:
    displays: list[str] = []
    chains: set[str] = set()
    for relative in paths:
        path = _project_path(project_root, relative, kind="file")
        displays.append(_relative(path, project_root))
        chains.update(
            chain
            for chain in _tree_attribute_chains(_parse_python(path))
            if chain.startswith("dependencies.")
        )
    return displays, frozenset(chains)


def check_runtime_ownership(project_root: Path = PROJECT_ROOT) -> BoundaryCheck:
    """Prove the generic runtime owns construction and every transport plane derives it."""

    backend = _project_path(project_root, PRODUCT_BACKEND_ROOT, kind="directory")
    main_path = _project_path(project_root, PRODUCT_MAIN, kind="file")
    core_runtime_path = _project_path(project_root, CORE_RUNTIME, kind="file")
    fastapi_runtime_path = _project_path(
        project_root, FASTAPI_RUNTIME, kind="file"
    )

    product_constructor_calls: list[dict[str, Any]] = []
    product_stream_calls: list[dict[str, Any]] = []
    product_files = (*_python_files(backend), main_path)
    for path in product_files:
        tree = _parse_python(path)
        display = _relative(path, project_root)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            call = _call_name(node.func)
            if call in FORBIDDEN_PRODUCT_RUNTIME_CONSTRUCTORS:
                product_constructor_calls.append(
                    {"path": display, "line": node.lineno, "constructor": call}
                )
            if call == "astream_events":
                product_stream_calls.append(
                    {"path": display, "line": node.lineno, "call": call}
                )

    generic_runner_constructor_sites: dict[str, list[dict[str, Any]]] = {
        "RouteDeckOperationRunner": [],
        "RouteDeckNavigationRunner": [],
    }
    for path in _production_python_files(project_root):
        tree = _parse_python(path)
        display = _relative(path, project_root)
        for constructor in generic_runner_constructor_sites:
            generic_runner_constructor_sites[constructor].extend(
                {
                    "path": display,
                    "line": call.lineno,
                }
                for call in _constructor_calls(tree, constructor)
            )

    core_tree = _parse_python(core_runtime_path)
    runtime_builder = _function_definition(core_tree, "build_routedeck_runtime")
    builder_scope: ast.AST = runtime_builder or ast.Module(body=[], type_ignores=[])
    runner_calls = _assigned_constructor_calls(
        builder_scope, "RouteDeckOperationRunner"
    )
    navigation_calls = _assigned_constructor_calls(
        builder_scope, "RouteDeckNavigationRunner"
    )
    services_calls = _assigned_constructor_calls(
        builder_scope, "RouteDeckRuntimeServices"
    )
    runner_evidence = [
        {
            "line": line,
            "target": target,
            "constructor": _call_name(call.func),
        }
        for line, target, call in runner_calls
    ]
    navigation_evidence = [
        {
            "line": line,
            "target": target,
            "operation_runner": _keyword_expression(call, "operation_runner"),
        }
        for line, target, call in navigation_calls
    ]
    services_evidence = [
        {
            "line": line,
            "target": target,
            "runner": _keyword_expression(call, "runner"),
            "navigation": _keyword_expression(call, "navigation"),
        }
        for line, target, call in services_calls
    ]

    fastapi_tree = _parse_python(fastapi_runtime_path)
    dependency_calls = _constructor_calls(fastapi_tree, "RouteDeckDependencies")
    dependency_expressions = (
        {
            name: _keyword_expression(dependency_calls[0], name)
            for name in ("runner", "navigation", "projector", "store")
        }
        if len(dependency_calls) == 1
        else {}
    )
    services_aliases = [
        ast.unparse(node.value)
        for node in ast.walk(fastapi_tree)
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        and any(name == "services" for name in _assigned_names(node))
    ]

    consumer_groups = {
        "operations": (FASTAPI_ROUTES_ROOT / "operations.py",),
        "navigation": (FASTAPI_ROUTES_ROOT / "operations.py",),
        "conversation": (
            FASTAPI_ROUTES_ROOT / "conversation.py",
            Path("routedeck_fastapi/conversation_stream.py"),
        ),
        "private_forms": (
            FASTAPI_ROUTES_ROOT / "private_forms.py",
            Path("routedeck_fastapi/private_forms.py"),
        ),
        "events": (FASTAPI_ROUTES_ROOT / "events.py",),
    }
    consumer_evidence: dict[str, Any] = {}
    consumer_chains: dict[str, frozenset[str]] = {}
    for name, paths in consumer_groups.items():
        displays, chains = _dependency_chains(project_root, paths)
        consumer_chains[name] = chains
        consumer_evidence[name] = {
            "paths": displays,
            "derived_dependencies": sorted(chains),
        }

    invariants = {
        "product_has_no_runtime_constructors": not product_constructor_calls,
        "product_has_no_astream_events_calls": not product_stream_calls,
        "core_builds_exactly_one_operation_runner": (
            len(runner_calls) == 1
            and runner_calls[0][1] == "runner"
            and generic_runner_constructor_sites["RouteDeckOperationRunner"]
            == [{"path": CORE_RUNTIME.as_posix(), "line": runner_calls[0][0]}]
        ),
        "core_builds_exactly_one_navigation_runner": (
            len(navigation_calls) == 1
            and navigation_calls[0][1] == "navigation"
            and generic_runner_constructor_sites["RouteDeckNavigationRunner"]
            == [
                {
                    "path": CORE_RUNTIME.as_posix(),
                    "line": navigation_calls[0][0],
                }
            ]
        ),
        "navigation_receives_local_runner": (
            len(navigation_calls) == 1
            and _keyword_expression(navigation_calls[0][2], "operation_runner")
            == "runner"
        ),
        "runtime_services_receive_local_runner_and_navigation": (
            len(services_calls) == 1
            and services_calls[0][1] == "services"
            and _keyword_expression(services_calls[0][2], "runner") == "runner"
            and _keyword_expression(services_calls[0][2], "navigation")
            == "navigation"
        ),
        "fastapi_derives_runtime_services": (
            services_aliases == ["runtime.services"]
            and dependency_expressions
            == {
                "runner": "services.runner",
                "navigation": "services.navigation",
                "projector": "services.projector",
                "store": "services.store",
            }
        ),
        "operation_routes_use_derived_runner": any(
            chain.startswith("dependencies.runner")
            for chain in consumer_chains["operations"]
        ),
        "navigation_routes_use_derived_navigation": any(
            chain.startswith("dependencies.navigation")
            for chain in consumer_chains["navigation"]
        ),
        "conversation_uses_derived_runtime_dependencies": (
            any(
                chain.startswith("dependencies.runner")
                for chain in consumer_chains["conversation"]
            )
            and any(
                chain.startswith("dependencies.store")
                for chain in consumer_chains["conversation"]
            )
        ),
        "private_forms_use_derived_runtime_dependencies": (
            any(
                chain.startswith("dependencies.runner")
                for chain in consumer_chains["private_forms"]
            )
            and any(
                chain.startswith("dependencies.store")
                for chain in consumer_chains["private_forms"]
            )
        ),
        "events_use_derived_store": any(
            chain.startswith("dependencies.store")
            for chain in consumer_chains["events"]
        ),
    }
    violations = [
        f"runtime ownership invariant failed:{name}"
        for name, passed in invariants.items()
        if not passed
    ]
    return BoundaryCheck(
        name="runtime_ownership",
        evidence={
            "forbidden_product_constructors": sorted(
                FORBIDDEN_PRODUCT_RUNTIME_CONSTRUCTORS
            ),
            "product_constructor_calls": product_constructor_calls,
            "product_astream_events_calls": product_stream_calls,
            "generic_runner_constructor_sites": generic_runner_constructor_sites,
            "core_runtime": {
                "path": CORE_RUNTIME.as_posix(),
                "builder": (
                    runtime_builder.name if runtime_builder is not None else None
                ),
                "operation_runner_constructors": runner_evidence,
                "navigation_runner_constructors": navigation_evidence,
                "runtime_services_constructors": services_evidence,
            },
            "fastapi_runtime": {
                "path": FASTAPI_RUNTIME.as_posix(),
                "services_aliases": services_aliases,
                "dependency_expressions": dependency_expressions,
            },
            "transport_consumers": consumer_evidence,
            "invariants": invariants,
            "proof_scope": (
                "AST constructor, event-stream call, runtime-service derivation, "
                "and transport dependency-consumption proof."
            ),
        },
        violations=tuple(sorted(violations)),
    )


def _normalize_symbol(name: str) -> str:
    with_boundaries = re.sub(r"(?<!^)(?=[A-Z])", "_", name)
    return re.sub(r"_+", "_", with_boundaries).lower()


def _assigned_names(node: ast.Assign | ast.AnnAssign) -> Iterable[str]:
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    for target in targets:
        if isinstance(target, ast.Name):
            yield target.id


def check_source_policy_scan(project_root: Path = PROJECT_ROOT) -> BoundaryCheck:
    backend = _project_path(project_root, PRODUCT_BACKEND_ROOT, kind="directory")
    main_path = _project_path(project_root, PRODUCT_MAIN, kind="file")
    frontend = _project_path(project_root, FRONTEND_SOURCE_ROOT, kind="directory")
    violations: list[str] = []
    python_files = (*_python_files(backend), main_path)
    inspected_symbols = 0
    for path in python_files:
        tree = _parse_python(path)
        display = _relative(path, project_root)
        for line, module in _imported_modules(tree):
            if _is_forbidden(module, (*PRODUCTION_TEST_MODULES, "re", "regex")):
                violations.append(
                    f"{display}:{line}:prohibited production import:{module}"
                )
        for node in ast.walk(tree):
            node_line = getattr(node, "lineno", 0)
            names: Iterable[str] = ()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names = (node.name,)
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                names = _assigned_names(node)
            for name in names:
                inspected_symbols += 1
                normalized = _normalize_symbol(name)
                matched = [
                    token for token in FORBIDDEN_POLICY_SYMBOLS if token in normalized
                ]
                if matched:
                    violations.append(
                        f"{display}:{node_line}:prohibited policy symbol:{name}:{','.join(matched)}"
                    )
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and _attribute_chain(node.func.value) in {"re", "regex"}
            ):
                violations.append(
                    f"{display}:{node.lineno}:regex-driven production dispatch:{node.func.attr}"
                )
    frontend_files = _typescript_production_files(frontend)
    for path in frontend_files:
        text = path.read_text(encoding="utf-8")
        code_literals = _typescript_string_literals(text)
        if "new RegExp(" in text or "RegExp(" in text:
            violations.append(
                f"{_relative(path, project_root)}:RegExp production routing is prohibited"
            )
        for line, value in code_literals:
            if value.startswith(("routedeck_testing", "@routedeck/testing")):
                violations.append(
                    f"{_relative(path, project_root)}:{line}:test harness import in production"
                )
    return BoundaryCheck(
        name="source_policy_scan",
        evidence={
            "python_roots": [PRODUCT_BACKEND_ROOT.as_posix(), PRODUCT_MAIN.as_posix()],
            "frontend_root": FRONTEND_SOURCE_ROOT.as_posix(),
            "python_file_count": len(python_files),
            "frontend_file_count": len(frontend_files),
            "inspected_symbol_count": inspected_symbols,
            "forbidden_test_modules": list(PRODUCTION_TEST_MODULES),
            "forbidden_policy_symbols": list(FORBIDDEN_POLICY_SYMBOLS),
            "proof_scope": (
                "Exact structural scan for test fixtures/mocks, regex routing, and "
                "named phrase/keyword/canned/fallback maps. Semantic fallback execution "
                "remains covered by architecture and runtime tests."
            ),
        },
        violations=tuple(sorted(set(violations))),
    )


def _check_feature_declarations(project_root: Path) -> tuple[dict[str, Any], list[str]]:
    feature_root = _project_path(project_root, FEATURE_ROOT, kind="directory")
    declarations = tuple(sorted(feature_root.glob("*/feature.py")))
    violations: list[str] = []
    evidence: list[dict[str, Any]] = []
    if not declarations:
        violations.append(f"{FEATURE_ROOT.as_posix()}:no feature declarations found")
    for path in declarations:
        tree = _parse_python(path)
        display = _relative(path, project_root)
        forbidden_imports = [
            {"line": line, "module": module}
            for line, module in _imported_modules(tree)
            if _is_forbidden(module, (*HTTP_CLIENT_MODULES, "fastapi"))
            or "medusa.client" in module
        ]
        store_literals = [
            {"line": line, "value": value}
            for line, value in _string_literals(tree)
            if _is_store_path(value)
        ]
        has_feature = any(
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "FEATURE"
                for target in node.targets
            )
            and isinstance(node.value, ast.Call)
            and _call_name(node.value.func) == "Feature"
            for node in ast.walk(tree)
        )
        evidence.append(
            {
                "path": display,
                "has_feature": has_feature,
                "forbidden_imports": forbidden_imports,
                "store_literals": store_literals,
            }
        )
        if not has_feature:
            violations.append(f"{display}:missing declarative FEATURE")
        if forbidden_imports or store_literals:
            violations.append(
                f"{display}:feature declaration owns transport/client code"
            )
    composition_path = _project_path(
        project_root,
        PRODUCT_BACKEND_ROOT / "composition.py",
        kind="file",
    )
    composition_tree = _parse_python(composition_path)
    forbidden_composition_calls = [
        {"line": node.lineno, "call": _call_name(node.func)}
        for node in ast.walk(composition_tree)
        if isinstance(node, ast.Call)
        and _call_name(node.func) in {"model_copy", "Transition"}
    ]
    forbidden_transition_keywords = [
        node.lineno
        for node in ast.walk(composition_tree)
        if isinstance(node, ast.Call)
        and any(keyword.arg == "transitions" for keyword in node.keywords)
    ]
    composition_source = composition_path.read_text(encoding="utf-8")
    if (
        forbidden_composition_calls
        or forbidden_transition_keywords
        or "_COMPOSED_" in composition_source
    ):
        violations.append(
            f"{_relative(composition_path, project_root)}:composition owns graph assembly"
        )
    return {
        "declarations": evidence,
        "composition": {
            "path": _relative(composition_path, project_root),
            "forbidden_calls": forbidden_composition_calls,
            "transition_keywords": forbidden_transition_keywords,
            "has_composed_prefix": "_COMPOSED_" in composition_source,
        },
    }, violations


def _check_langgraph_topology(project_root: Path) -> tuple[dict[str, Any], list[str]]:
    adapter_root = _project_path(
        project_root, Path("routedeck_langgraph"), kind="directory"
    )
    violations: list[str] = []
    scanned: list[str] = []
    for path in _python_files(adapter_root):
        tree = _parse_python(path)
        display = _relative(path, project_root)
        scanned.append(display)
        for line, module in _imported_modules(tree):
            if module == "langgraph.graph" or module.startswith("langgraph.graph."):
                violations.append(
                    f"{display}:{line}:adapter imports LangGraph topology:{module}"
                )
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == "StateGraph":
                violations.append(
                    f"{display}:{node.lineno}:adapter references StateGraph"
                )
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in TOPOLOGY_MUTATORS
            ):
                violations.append(
                    f"{display}:{node.lineno}:adapter mutates graph topology:{node.func.attr}"
                )
    return {
        "scanned_files": scanned,
        "forbidden_topology_mutators": list(TOPOLOGY_MUTATORS),
    }, violations


def _check_standalone_medusa_server(
    project_root: Path,
) -> tuple[dict[str, Any], list[str]]:
    server_root = project_root / MEDUSA_SERVER_ROOT
    compose_path = project_root / MEDUSA_COMPOSE
    violations: list[str] = []
    required_files = {
        relative.as_posix(): (server_root / relative).is_file()
        for relative in MEDUSA_REQUIRED_SOURCE_FILES
    }
    for relative, exists in required_files.items():
        if not exists:
            violations.append(
                f"{MEDUSA_SERVER_ROOT.as_posix()}/{relative}:required standalone source missing"
            )

    compose_contexts: list[str] = []
    if not compose_path.is_file():
        violations.append(f"{MEDUSA_COMPOSE.as_posix()}:required Compose file missing")
    else:
        compose_text = compose_path.read_text(encoding="utf-8")
        compose_contexts = [
            stripped.partition(":")[2].strip()
            for line in compose_text.splitlines()
            if (stripped := line.strip()).startswith("context:")
        ]
        expected_contexts = [MEDUSA_COMPOSE_CONTEXT, MEDUSA_COMPOSE_CONTEXT]
        if compose_contexts != expected_contexts:
            violations.append(
                f"{MEDUSA_COMPOSE.as_posix()}:Medusa build contexts must be exactly "
                f"{expected_contexts!r}, found {compose_contexts!r}"
            )
        if "test_targets" in compose_text:
            violations.append(
                f"{MEDUSA_COMPOSE.as_posix()}:external test_targets dependency is prohibited"
            )

    package_manager: str | None = None
    runtime_dependencies: dict[str, str] = {}
    package_path = server_root / "package.json"
    if package_path.is_file():
        package = json.loads(package_path.read_text(encoding="utf-8"))
        package_manager = package.get("packageManager")
        runtime_dependencies = dict(package.get("dependencies", {}))
        if package_manager != MEDUSA_PACKAGE_MANAGER:
            violations.append(
                f"{MEDUSA_SERVER_ROOT.as_posix()}/package.json:packageManager must be "
                f"{MEDUSA_PACKAGE_MANAGER}"
            )
        for dependency, expected_version in MEDUSA_PINNED_RUNTIME_DEPENDENCIES.items():
            actual_version = runtime_dependencies.get(dependency)
            if actual_version != expected_version:
                violations.append(
                    f"{MEDUSA_SERVER_ROOT.as_posix()}/package.json:{dependency} must be "
                    f"pinned to {expected_version}, found {actual_version!r}"
                )

    lockfile_version: int | None = None
    lock_runtime_dependencies: dict[str, str] = {}
    lock_path = server_root / "package-lock.json"
    if lock_path.is_file():
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        lockfile_version = lock.get("lockfileVersion")
        lock_root = lock.get("packages", {}).get("", {})
        lock_runtime_dependencies = dict(lock_root.get("dependencies", {}))
        if lockfile_version != 3:
            violations.append(
                f"{MEDUSA_SERVER_ROOT.as_posix()}/package-lock.json:lockfileVersion must be 3"
            )
        if lock_runtime_dependencies != runtime_dependencies:
            violations.append(
                f"{MEDUSA_SERVER_ROOT.as_posix()}/package-lock.json:root runtime dependencies "
                "do not match package.json"
            )

    docker_base: str | None = None
    dockerfile_path = server_root / "Dockerfile"
    if dockerfile_path.is_file():
        dockerfile_lines = dockerfile_path.read_text(encoding="utf-8").splitlines()
        from_lines = [line.removeprefix("FROM ").strip() for line in dockerfile_lines if line.startswith("FROM ")]
        docker_base = from_lines[0] if len(from_lines) == 1 else None
        if docker_base != MEDUSA_DOCKER_BASE:
            violations.append(
                f"{MEDUSA_SERVER_ROOT.as_posix()}/Dockerfile:base image must be exactly "
                f"{MEDUSA_DOCKER_BASE}"
            )

    evidence = {
        "source_root": MEDUSA_SERVER_ROOT.as_posix(),
        "compose_file": MEDUSA_COMPOSE.as_posix(),
        "compose_build_contexts": compose_contexts,
        "required_source_files": required_files,
        "package_manager": package_manager,
        "pinned_runtime_dependencies": runtime_dependencies,
        "lockfile_version": lockfile_version,
        "docker_base": docker_base,
    }
    return evidence, violations


def _check_product_frontend_assistant_protocol(
    project_root: Path,
) -> tuple[dict[str, Any], list[str]]:
    frontend = _project_path(project_root, FRONTEND_SOURCE_ROOT, kind="directory")
    files = _typescript_production_files(frontend)
    violations: list[str] = []
    direct_calls: list[dict[str, Any]] = []
    event_switches: list[dict[str, Any]] = []
    for path in files:
        display = _relative(path, project_root)
        source = path.read_text(encoding="utf-8")
        masked = _typescript_code_mask(source)
        masked_lines = masked.splitlines()
        for match in re.finditer(r"\.\s*streamAssistantTurn\s*\(", masked):
            line = source.count("\n", 0, match.start()) + 1
            direct_calls.append({"path": display, "line": line})
            violations.append(
                f"{display}:{line}:product frontend calls streamAssistantTurn directly"
            )
        for line, value in _typescript_string_literals(source):
            if value not in ASSISTANT_STREAM_EVENT_DISCRIMINANTS:
                continue
            masked_line = masked_lines[line - 1] if line <= len(masked_lines) else ""
            if re.search(r"\bcase\b", masked_line) is None:
                continue
            event_switches.append({"path": display, "line": line, "event": value})
            violations.append(
                f"{display}:{line}:product frontend switches over generic assistant event:{value}"
            )
    return {
        "scanned_files": [_relative(path, project_root) for path in files],
        "direct_stream_assistant_turn_calls": direct_calls,
        "generic_assistant_event_switches": event_switches,
        "assistant_event_discriminants": sorted(
            ASSISTANT_STREAM_EVENT_DISCRIMINANTS
        ),
    }, sorted(set(violations))


def _check_framework_product_vocabulary(
    project_root: Path,
) -> tuple[dict[str, Any], list[str]]:
    files: list[Path] = []
    for relative in FRAMEWORK_TYPESCRIPT_ROOTS:
        root = _project_path(project_root, relative, kind="directory")
        files.extend(_typescript_production_files(root))
    for relative in FRAMEWORK_PYTHON_ROOTS:
        root = _project_path(project_root, relative, kind="directory")
        files.extend(
            path
            for path in _python_files(root)
            if "tests" not in path.relative_to(root).parts
            and not path.name.startswith("generated")
        )
    inspected = tuple(sorted(set(files), key=lambda path: path.as_posix()))
    matches: list[dict[str, Any]] = []
    violations: list[str] = []
    for path in inspected:
        display = _relative(path, project_root)
        for line, source_line in enumerate(
            path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            for match in FORBIDDEN_FRAMEWORK_PRODUCT_VOCABULARY.finditer(source_line):
                vocabulary = match.group(0)
                matches.append(
                    {"path": display, "line": line, "vocabulary": vocabulary}
                )
                violations.append(
                    f"{display}:{line}:forbidden product vocabulary:{vocabulary}"
                )
    return {
        "scanned_files": [_relative(path, project_root) for path in inspected],
        "matches": matches,
        "forbidden_pattern": FORBIDDEN_FRAMEWORK_PRODUCT_VOCABULARY.pattern,
    }, sorted(set(violations))


def check_architectural_review(project_root: Path = PROJECT_ROOT) -> BoundaryCheck:
    core = _project_path(project_root, CORE_ROOT, kind="directory")
    core_product_violations = scan_python_imports(core, ("medusa_agent",))
    feature_evidence, feature_violations = _check_feature_declarations(project_root)
    topology_evidence, topology_violations = _check_langgraph_topology(project_root)
    standalone_evidence, standalone_violations = _check_standalone_medusa_server(
        project_root
    )
    assistant_protocol_evidence, assistant_protocol_violations = (
        _check_product_frontend_assistant_protocol(project_root)
    )
    vocabulary_evidence, vocabulary_violations = (
        _check_framework_product_vocabulary(project_root)
    )
    transport = check_product_transport_separation(project_root)
    runtime_ownership = check_runtime_ownership(project_root)
    invariants = {
        "framework_core_has_no_product_imports": not core_product_violations,
        "feature_declarations_have_no_transport": not feature_violations,
        "langgraph_adapter_does_not_own_topology": not topology_violations,
        "standalone_medusa_demo_uses_repo_local_pinned_server": (
            not standalone_violations
        ),
        "generic_runtime_supplies_all_transport_planes": (
            not transport.violations and not runtime_ownership.violations
        ),
        "product_frontend_does_not_own_assistant_stream_protocol": (
            not assistant_protocol_violations
        ),
        "framework_production_copy_is_product_neutral": not vocabulary_violations,
    }
    violations = [
        *(f"core_product_import:{item}" for item in core_product_violations),
        *(f"feature_declaration:{item}" for item in feature_violations),
        *(f"langgraph_topology:{item}" for item in topology_violations),
        *(f"standalone_medusa_server:{item}" for item in standalone_violations),
        *(
            f"assistant_stream_protocol:{item}"
            for item in assistant_protocol_violations
        ),
        *(f"framework_vocabulary:{item}" for item in vocabulary_violations),
        *(f"transport_separation:{item}" for item in transport.violations),
        *(
            f"runtime_ownership:{item}"
            for item in runtime_ownership.violations
        ),
    ]
    return BoundaryCheck(
        name="architectural_review",
        evidence={
            "invariants": invariants,
            "feature_declarations": feature_evidence,
            "langgraph_adapter": topology_evidence,
            "standalone_medusa_server": standalone_evidence,
            "product_frontend_assistant_protocol": assistant_protocol_evidence,
            "framework_product_vocabulary": vocabulary_evidence,
            "transport_router_inventory": transport.evidence,
            "runtime_ownership": runtime_ownership.evidence,
        },
        violations=tuple(sorted(violations)),
    )


def build_boundary_report(project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    resolved_root = project_root.resolve()
    checks = (
        check_core_imports(resolved_root),
        check_store_endpoint_inventory(resolved_root),
        check_handler_client_port(resolved_root),
        check_browser_network(resolved_root),
        check_product_transport_separation(resolved_root),
        check_runtime_ownership(resolved_root),
        check_source_policy_scan(resolved_root),
        check_architectural_review(resolved_root),
    )
    if tuple(check.name for check in checks) != REQUIRED_CHECK_NAMES:
        raise RuntimeError(
            "Boundary check order drifted from the approved release contract"
        )
    violation_count = sum(len(check.violations) for check in checks)
    return {
        "schema_version": BOUNDARY_REPORT_SCHEMA_VERSION,
        "status": "pass" if violation_count == 0 else "fail",
        "violation_count": violation_count,
        "checks": [check.as_dict() for check in checks],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check RouteDeck framework/product dependency boundaries."
    )
    parser.add_argument("--json", required=True, type=Path, dest="json_path")
    args = parser.parse_args(argv)

    report = build_boundary_report()
    args.json_path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    args.json_path.write_text(f"{rendered}\n", encoding="utf-8")
    print(rendered)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
