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
)
RETIRED_PRODUCT_ENDPOINTS = (
    "/api/medusa-agent/state",
    "/api/medusa-agent/route-manifest",
    "/api/medusa-agent/projection",
    "/api/medusa-agent/route-stream",
    "/api/medusa-agent/action",
    "/api/medusa-agent/agent/stream",
    "/api/medusa-agent/inspect",
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
        "ApplicationSpec",
        "FeatureSpec",
        "NodeSpec",
        "SurfaceSpec",
        "RouteEntrySpec",
        "PrivateFormBindingSpec",
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

    assert "POST /api/medusa-agent/chat" in references
    for endpoint in GENERIC_ROUTEDECK_ENDPOINTS:
        assert endpoint in references
    for endpoint in RETIRED_PRODUCT_ENDPOINTS:
        assert endpoint not in references
    assert PRODUCT_SPECIFIC_ROUTEDECK_ROUTE.search(references) is None


def test_generic_routedeck_and_product_chat_routers_are_composed_once() -> None:
    router = _read("routedeck_fastapi/router.py")
    chat = _read("examples/medusa-agent/backend/medusa_agent/api/chat.py")
    main = _read("examples/medusa-agent/backend/main.py")

    assert 'APIRouter(prefix="/api/routedeck"' in router
    for decorator in (
        '@router.get("/contract")',
        '@router.post("/sessions", status_code=201)',
        '@router.get("/session")',
        '@router.post("/navigation")',
        '@router.post("/dispatch")',
        '@router.get("/events")',
        '@router.get("/private-forms/{form_id}")',
        '@router.put("/private-forms/{form_id}")',
        '@router.get("/inspect")',
    ):
        assert decorator in router

    assert 'APIRouter(prefix="/api/medusa-agent"' in chat
    assert '@router.post("/chat")' in chat
    assert main.count("create_routedeck_router_from_provider(") == 1
    assert main.count("create_medusa_chat_router(") == 1
    assert "application.include_router(health_router)" in main


def test_medusa_application_is_compiled_from_modular_feature_specs() -> None:
    composition = _read("examples/medusa-agent/backend/medusa_agent/composition.py")
    feature_paths = sorted(
        (ROOT / "examples/medusa-agent/backend/medusa_agent/features").glob(
            "*/feature.py"
        )
    )
    feature_text = "\n".join(path.read_text(encoding="utf-8") for path in feature_paths)

    assert len(feature_paths) == 4
    assert "MEDUSA_APP_SPEC = ApplicationSpec(" in composition
    for contract_name in (
        "FeatureSpec(",
        "NodeSpec(",
        "SurfaceSpec(",
        "RouteEntrySpec(",
        "RouteParameterBinding(",
        "PrivateFormBindingSpec(",
    ):
        assert contract_name in feature_text
    for runtime_name in (
        "compile_app(",
        "bind_app(",
        "RouteDeckOperationRunner(",
        "RouteDeckNavigationRunner(",
        "MedusaStoreClient",
    ):
        assert runtime_name in composition


def test_langgraph_adapter_wraps_execution_without_owning_topology() -> None:
    middleware = _read("routedeck_langgraph/middleware.py")
    tool_wrapper = _read("routedeck_langgraph/tool_wrapper.py")
    legacy_builder = _read("routedeck_langgraph/graph.py")
    agent = _read("examples/medusa-agent/backend/medusa_agent/agent.py")

    assert "class RouteDeckMiddleware(" in middleware
    assert (
        "AgentMiddleware[AgentState[Any], RouteDeckInvocationContext, Any]"
        in middleware
    )
    assert "class RouteDeckToolWrapper:" in tool_wrapper
    assert "RouteDeckOperationRunner" in tool_wrapper
    assert "raise RouteDeckTopologyBuilderDeprecatedError(" in legacy_builder
    assert "no longer builds or" in legacy_builder
    assert "mutates LangGraph topology" in legacy_builder
    assert "agent = create_agent(" in agent
    assert "middleware = RouteDeckMiddleware(runtime)" in agent
    assert "wrapper = RouteDeckToolWrapper(runtime)" in agent
    assert "StateGraph(" not in agent


def test_private_forms_and_exact_browser_history_are_framework_owned() -> None:
    private_contract = _read("routedeck_core/contracts/surfaces.py")
    router = _read("routedeck_fastapi/router.py")
    navigation = _read("routedeck_core/navigation/transactions.py")
    browser_history = _read("packages/core/src/routing/history.ts")
    browser_store = _read("packages/core/src/store/store.ts")
    contact_feature = _read(
        "examples/medusa-agent/backend/medusa_agent/features/checkout/feature.py"
    )

    assert "class PrivateFormBindingSpec" in private_contract
    assert "CHECKOUT_PRIVATE_FORM_BINDING = PrivateFormBindingSpec(" in contact_feature
    assert (
        contact_feature.count("private_form_binding=CHECKOUT_PRIVATE_FORM_BINDING") == 2
    )
    assert '@router.get("/private-forms/{form_id}")' in router
    assert '@router.put("/private-forms/{form_id}")' in router
    assert "save_private_blob(" in router
    assert "revision = current_draft.revision + 1 if current_draft else 1" in router

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
    assert 'kind: "restore_history_entry"' in browser_store


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
