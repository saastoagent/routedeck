from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTIVE_REFERENCE_FILES = (
    "README.md",
    "structure.md",
    "architecture/code-map.md",
    "test_index/README.md",
    "docs/route-deck-reference.md",
    "docs/medusa-agent-reference-app.md",
    "examples/medusa-agent/README.md",
)
GENERIC_ROUTEDECK_ENDPOINTS = (
    "/api/routedeck/contract",
    "/api/routedeck/sessions",
    "/api/routedeck/session",
    "/api/routedeck/navigation",
    "/api/routedeck/dispatch",
    "/api/routedeck/reviews/{review_id}/accept",
    "/api/routedeck/reviews/{review_id}/reject",
    "/api/routedeck/events",
    "/api/routedeck/private-forms/{form_id}",
    "/api/routedeck/inspect",
    "/api/routedeck/conversation/assistant-turn",
)
RETIRED_PRODUCT_ENDPOINTS = (
    "/api/medusa-agent/state",
    "/api/medusa-agent/route-manifest",
    "/api/medusa-agent/projection",
    "/api/medusa-agent/route-stream",
    "/api/medusa-agent/action",
    "/api/medusa-agent/agent/stream",
    "/api/medusa-agent/inspect",
    "/api/medusa-agent/conversation/entry",
)
DELETED_RUNTIME_AND_TRANSPORT_PATHS = (
    "examples/medusa-agent/backend/medusa_agent/runtime_factory.py",
    "examples/medusa-agent/backend/medusa_agent/agent_driver.py",
    "examples/medusa-agent/backend/medusa_agent/api/entry.py",
    "examples/medusa-agent/backend/medusa_agent/entry_conversation.py",
    "examples/medusa-agent/frontend/src/app/conversationEntryClient.ts",
    "routedeck_fastapi/conversation.py",
    "routedeck_fastapi/conversation_dependencies.py",
    "packages/react/src/conversation/state.ts",
    "packages/react/src/conversation/transitions.ts",
)
FORBIDDEN_PRODUCT_RUNTIME_CONSTRUCTORS = (
    "RouteDeckOperationRunner(",
    "RouteDeckNavigationRunner(",
    "RouteDeckDependencies(",
    "RouteDeckLangGraphAgentDriver(",
)
PRODUCT_SPECIFIC_ROUTEDECK_ROUTE = re.compile(
    r"/api/routedeck/(?:medusa|catalog|product|cart|checkout|shipping|payment|order|fulfillment)(?:/|\b)",
    re.IGNORECASE,
)


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _combined(*relative_paths: str) -> str:
    return "\n".join(_read(path) for path in relative_paths)


def test_active_references_lock_the_compiled_framework_and_product_boundaries() -> None:
    route_deck_reference = _read("docs/route-deck-reference.md")
    medusa_reference = _read("docs/medusa-agent-reference-app.md")
    references = _combined(*ACTIVE_REFERENCE_FILES)

    assert "Status: canonical framework reference" in route_deck_reference
    assert "Status: active source of truth" in medusa_reference
    for contract_name in (
        "Application",
        "Feature",
        "Node",
        "Surface",
        "RouteEntry",
        "PrivateFormBinding",
        "RouteDeckOperationRunner",
        "RouteDeckMiddleware",
        "RouteDeckToolWrapper",
        "MedusaStoreClient",
        "HttpMedusaStoreClient",
        "pp_system_default",
    ):
        assert contract_name in references

    assert "Local Windows execution is authoritative" in medusa_reference
    assert "OPENAI_API_KEY" in medusa_reference
    assert "No key means no chat agent is composed" in " ".join(
        medusa_reference.split()
    )


def test_active_references_name_only_the_current_public_api_planes() -> None:
    references = _combined(*ACTIVE_REFERENCE_FILES)

    assert "POST /api/routedeck/chat" in references
    for endpoint in GENERIC_ROUTEDECK_ENDPOINTS:
        assert endpoint in references
    for endpoint in RETIRED_PRODUCT_ENDPOINTS:
        assert endpoint not in references
    assert PRODUCT_SPECIFIC_ROUTEDECK_ROUTE.search(references) is None


def test_routedeck_routers_and_product_entry_are_composed_once() -> None:
    router = _read("routedeck_fastapi/router.py")
    route_modules = {
        name: _read(f"routedeck_fastapi/routes/{name}.py")
        for name in (
            "contract",
            "sessions",
            "operations",
            "conversation",
            "events",
            "private_forms",
            "inspection",
        )
    }
    main = _read("examples/medusa-agent/backend/main.py")

    assert 'APIRouter(prefix="/api/routedeck"' in router
    expected_factories = (
        "create_contract_routes",
        "create_session_routes",
        "create_operation_routes",
        "create_conversation_routes",
        "create_event_routes",
        "create_private_form_routes",
        "create_inspection_routes",
    )
    for factory in expected_factories:
        assert router.count(f"{factory}(") == 1
    expected_decorators = {
        "contract": ('@router.get("/contract")',),
        "sessions": (
            '@router.post("/sessions", status_code=201)',
            '@router.get("/session")',
        ),
        "operations": (
            '@router.post("/navigation")',
            '@router.post("/dispatch")',
            '@router.post("/reviews/{review_id}/accept")',
            '@router.post("/reviews/{review_id}/reject")',
        ),
        "conversation": (
            '@router.get("/conversation")',
            '@router.post("/chat")',
            '@router.post("/conversation/assistant-turn")',
        ),
        "events": ('@router.get("/events")',),
        "private_forms": (
            '@router.get("/private-forms/{form_id}")',
            '@router.put("/private-forms/{form_id}")',
        ),
        "inspection": ('@router.get("/inspect")',),
    }
    for module, decorators in expected_decorators.items():
        for decorator in decorators:
            assert decorator in route_modules[module]

    assert main.count("create_routedeck_router_from_runtime_provider(") == 1
    assert "create_routedeck_router_from_provider" not in main
    assert "create_routedeck_conversation_router" not in main
    assert main.count("application.include_router(health_router)") == 1


def test_medusa_application_is_compiled_from_modular_features() -> None:
    composition = _read("examples/medusa-agent/backend/medusa_agent/composition.py")
    bindings = _read("examples/medusa-agent/backend/medusa_agent/bindings.py")
    runtime = _read("examples/medusa-agent/backend/medusa_agent/runtime.py")
    core_runtime = _read("routedeck_core/runtime.py")
    product_backend = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(
            (ROOT / "examples/medusa-agent/backend/medusa_agent").rglob("*.py")
        )
    )
    feature_paths = sorted(
        (ROOT / "examples/medusa-agent/backend/medusa_agent/features").glob(
            "*/feature.py"
        )
    )
    feature_text = "\n".join(path.read_text(encoding="utf-8") for path in feature_paths)

    assert len(feature_paths) == 4
    assert "MEDUSA_APP = Application(" in composition
    assert "model_copy" not in composition
    assert "Transition(" not in composition
    assert "_COMPOSED_" not in composition
    for contract_name in (
        "Feature(",
        "Node(",
        "Surface(",
        "RouteEntry(",
        "RouteParameterBinding(",
        "PrivateFormBinding(",
    ):
        assert contract_name in feature_text
    assert "compile_app(" in composition
    assert "bind_app(" in bindings
    assert "MedusaStoreClient" in bindings
    assert "open_sqlalchemy_routedeck_runtime(" in runtime
    assert "compile_medusa_app()" in runtime
    assert "bind_medusa_app(" in runtime
    assert "RouteDeckLangGraphDriverFactory(" in runtime
    assert "HttpMedusaStoreClient(" in runtime
    assert "runner = RouteDeckOperationRunner(" in core_runtime
    assert "navigation = RouteDeckNavigationRunner(" in core_runtime
    assert "services = RouteDeckRuntimeServices(" in core_runtime
    for constructor in FORBIDDEN_PRODUCT_RUNTIME_CONSTRUCTORS:
        assert constructor not in product_backend
    assert ".astream_events(" not in product_backend


def test_deleted_product_runtime_and_transport_paths_stay_absent() -> None:
    for relative_path in DELETED_RUNTIME_AND_TRANSPORT_PATHS:
        assert not (ROOT / relative_path).exists(), relative_path


def test_medusa_frontend_uses_only_the_generic_conversation_client() -> None:
    frontend_root = ROOT / "examples/medusa-agent/frontend/src"
    production = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(frontend_root.rglob("*.ts*"))
        if "tests" not in path.relative_to(frontend_root).parts
        and ".test." not in path.name
    )

    assert "createRouteDeckAgentClient" in production
    assert "conversationEntryClient" not in production
    assert "/api/medusa-agent/conversation/entry" not in production


def test_langgraph_adapter_wraps_execution_without_owning_topology() -> None:
    middleware = _read("routedeck_langgraph/middleware.py")
    tool_wrapper = _read("routedeck_langgraph/tool_wrapper.py")
    agent = _read("examples/medusa-agent/backend/medusa_agent/agent.py")

    assert "class RouteDeckMiddleware(" in middleware
    assert (
        "AgentMiddleware[AgentState[Any], RouteDeckInvocationContext, Any]"
        in middleware
    )
    assert "class RouteDeckToolWrapper:" in tool_wrapper
    assert "RouteDeckOperationRunner" in tool_wrapper
    assert not (ROOT / "routedeck_langgraph/graph.py").exists()
    assert not (ROOT / "routedeck_langgraph/transition.py").exists()
    assert not (ROOT / "routedeck_langgraph/validation.py").exists()
    assert "agent = create_agent(" in agent
    assert "middleware = RouteDeckMiddleware(runtime)" in agent
    assert "wrapper = RouteDeckToolWrapper(runtime)" in agent
    assert "StateGraph(" not in agent


def test_private_forms_and_exact_browser_history_are_framework_owned() -> None:
    private_contract = _read("routedeck_core/contracts/surfaces.py")
    private_form_transport = _combined(
        "routedeck_fastapi/routes/private_forms.py",
        "routedeck_fastapi/private_forms.py",
    )
    navigation = _read("routedeck_core/navigation/transactions.py")
    browser_history = _read("packages/core/src/routing/history.ts")
    browser_navigation = _read("packages/core/src/store/navigation.ts")
    contact_feature = _read(
        "examples/medusa-agent/backend/medusa_agent/features/checkout/feature.py"
    )

    assert "class PrivateFormBinding" in private_contract
    assert "CHECKOUT_PRIVATE_FORM_BINDING = PrivateFormBinding(" in contact_feature
    assert (
        contact_feature.count("private_form_binding=CHECKOUT_PRIVATE_FORM_BINDING") == 2
    )
    assert '@router.get("/private-forms/{form_id}")' in private_form_transport
    assert '@router.put("/private-forms/{form_id}")' in private_form_transport
    assert "save_private_blob(" in private_form_transport
    assert (
        "revision = current_draft.revision + 1 if current_draft else 1"
        in private_form_transport
    )

    for intent in (
        'OPEN_PATH = "open_path"',
        'BACK = "back"',
        'FORWARD = "forward"',
        'CANCEL = "cancel"',
        'RESTORE_HISTORY_ENTRY = "restore_history_entry"',
    ):
        assert intent in navigation
    assert "history_entry_id" in browser_history
    assert "pushState" in browser_history
    assert "replaceState" in browser_history
    assert 'kind: "restore_history_entry"' in browser_navigation


def test_current_python_and_javascript_versions_are_locked() -> None:
    pyproject = tomllib.loads(_read("pyproject.toml"))
    extras = pyproject["project"]["optional-dependencies"]
    requirements = {
        line.strip()
        for line in _read("examples/medusa-agent/backend/requirements.txt").splitlines()
        if line.strip()
    }
    python_pins = {
        "langgraph==1.2.9",
        "langchain==1.3.13",
        "langchain-openai==1.3.5",
        "fastapi==0.136.3",
        "httpx==0.28.1",
        "uvicorn==0.48.0",
        "pytest==9.0.3",
        "pytest-asyncio==1.4.0",
    }

    assert python_pins <= requirements
    assert set(extras["langgraph"]) == {
        "langgraph==1.2.9",
        "langchain==1.3.13",
        "langchain-openai==1.3.5",
    }
    assert set(extras["fastapi"]) == {
        "fastapi==0.136.3",
        "httpx==0.28.1",
        "uvicorn==0.48.0",
    }
    assert {"pytest==9.0.3", "pytest-asyncio==1.4.0"} <= set(extras["testing"])

    workspace = json.loads(_read("package.json"))
    frontend = json.loads(_read("examples/medusa-agent/frontend/package.json"))
    assert workspace["packageManager"] == "pnpm@11.7.0"
    assert workspace["engines"]["node"] == ">=22.13.0"
    assert workspace["devDependencies"]["typescript"] == "7.0.2"
    assert workspace["devDependencies"]["vitest"] == "4.1.10"
    assert frontend["dependencies"]["react"] == "19.2.7"
    assert frontend["dependencies"]["react-dom"] == "19.2.7"
    assert frontend["devDependencies"]["vite"] == "8.1.4"
    assert frontend["devDependencies"]["@vitejs/plugin-react"] == "6.0.3"
    assert frontend["devDependencies"]["jsdom"] == "29.1.1"


def test_release_contract_is_local_windows_and_protected() -> None:
    stack = _read("examples/medusa-agent/scripts/demo-stack.ps1")
    release = _read("examples/medusa-agent/scripts/release-verify.ps1")
    compose = _read("examples/medusa-agent/infra/compose.yaml")

    assert '$ProjectName = "routedeck-medusa-demo"' in stack
    for port in ("9100", "8098", "5198"):
        assert port in stack
        assert port in release
    assert "Win32NT" in release
    assert "local Windows development machine" in release
    assert "OPENAI_API_KEY is mandatory for release" in release
    assert "if (-not $ResetProtectedDemo)" in release
    assert '"-Action", "Reset"' in release
    assert "finally {" in release
    assert '"-Action", "Down"' in release
    assert '"run", "--rm", "--no-deps", "medusa-setup"' in stack
    assert "abort-on-container-exit" not in stack
    assert compose.count("start_period: 3m") >= 2


def test_public_readiness_metadata_exists() -> None:
    assert "MIT License" in _read("LICENSE")
    assert (ROOT / "THIRD_PARTY_NOTICES.md").exists()

    pyproject = tomllib.loads(_read("pyproject.toml"))
    assert pyproject["project"]["license"] == "MIT"
    assert (
        "License :: OSI Approved :: MIT License" in pyproject["project"]["classifiers"]
    )
