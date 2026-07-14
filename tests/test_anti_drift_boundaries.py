from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SUFFIXES = {".py", ".ts", ".tsx"}
PRODUCT_SPECIFIC_ROUTEDECK_ROUTE = re.compile(
    r"/api/routedeck/(?:medusa|catalog|product|cart|checkout|shipping|payment|order|fulfillment)(?:/|\b)",
    re.IGNORECASE,
)
LANGGRAPH_IMPORT = re.compile(
    r"^(?:from\s+langgraph\b|import\s+langgraph\b)", re.MULTILINE
)


def _read(relative_path: str | Path) -> str:
    path = relative_path if isinstance(relative_path, Path) else ROOT / relative_path
    return path.read_text(encoding="utf-8")


def _production_files(*relative_roots: str) -> list[Path]:
    files: list[Path] = []
    for relative_root in relative_roots:
        root = ROOT / relative_root
        candidates = (root,) if root.is_file() else root.rglob("*")
        for path in candidates:
            if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
                continue
            relative_parts = path.relative_to(ROOT).parts
            if "tests" in relative_parts or ".test." in path.name:
                continue
            files.append(path)
    return sorted(set(files))


def _combined(paths: list[Path]) -> str:
    return "\n".join(_read(path) for path in paths)


def test_framework_packages_stay_product_neutral() -> None:
    framework_files = _production_files(
        "routedeck_core",
        "routedeck_fastapi",
        "routedeck_sqlalchemy",
        "routedeck_langgraph",
        "packages/core/src",
        "packages/react/src",
    )
    framework_text = _combined(framework_files)

    assert "medusa_agent" not in framework_text.lower()
    assert PRODUCT_SPECIFIC_ROUTEDECK_ROUTE.search(framework_text) is None
    assert (
        LANGGRAPH_IMPORT.search(_combined(_production_files("routedeck_core"))) is None
    )


def test_medusa_frontend_uses_routedeck_conversation_and_product_entry_planes() -> None:
    frontend_text = _combined(_production_files("examples/medusa-agent/frontend/src"))
    route_deck_client = _read("examples/medusa-agent/frontend/src/routedeck/client.ts")
    chat_client = _read("packages/core/src/conversation/client.ts")
    entry_client = _read(
        "examples/medusa-agent/frontend/src/app/conversationEntryClient.ts"
    )

    assert 'from "@routedeck/core"' in frontend_text
    assert 'from "@routedeck/react"' in frontend_text
    assert 'baseUrl: "/api/routedeck"' in route_deck_client
    assert 'options.baseUrl ?? "/api/routedeck"' in chat_client
    assert "`${baseUrl}/chat`" in chat_client
    assert 'options.baseUrl ?? "/api/medusa-agent"' in entry_client
    for forbidden in (
        "@medusajs",
        "/store/",
        "127.0.0.1:9100",
        "http://localhost:9100",
    ):
        assert forbidden not in frontend_text.lower()
    assert PRODUCT_SPECIFIC_ROUTEDECK_ROUTE.search(frontend_text) is None


def test_store_http_is_confined_to_the_typed_medusa_client_package() -> None:
    backend_root = "examples/medusa-agent/backend/medusa_agent"
    client_root = ROOT / backend_root / "medusa/client"
    expected_owners = [client_root / "http.py", client_root / "transport.py"]
    protocol = _read(f"{backend_root}/medusa/client/protocol.py")
    transport_owners = []

    for path in _production_files(backend_root):
        text = _read(path).lower()
        if "httpx" in text or "/store/" in text or "/admin/" in text:
            transport_owners.append(path)

    assert transport_owners == expected_owners
    assert "class MedusaStoreClient(Protocol):" in protocol
    assert "class HttpMedusaStoreClient:" in _read(client_root / "http.py")


def test_feature_declarations_do_not_own_transport_or_agent_topology() -> None:
    feature_files = sorted(
        (ROOT / "examples/medusa-agent/backend/medusa_agent/features").glob(
            "*/feature.py"
        )
    )
    declarations = _combined(feature_files).lower()

    assert len(feature_files) == 4
    for forbidden in (
        "httpx",
        "/store/",
        "/admin/",
        "stategraph",
        "create_agent",
        "routedeckmiddleware",
        "routedecktoolwrapper",
        "medusastoreclient",
    ):
        assert forbidden not in declarations


def test_retired_slice_backend_and_frontend_paths_are_removed() -> None:
    removed_paths = (
        "examples/medusa-agent/backend/core",
        "examples/medusa-agent/backend/routes",
        "examples/medusa-agent/backend/services",
        "examples/medusa-agent/frontend/src/App.tsx",
        "examples/medusa-agent/frontend/src/styles.css",
        "examples/medusa-agent/frontend/src/hooks/useRouteDeckProjection.ts",
        "examples/medusa-agent/frontend/src/hooks/useRouteDeckEvents.ts",
        "examples/medusa-agent/frontend/src/hooks/useSSEChat.ts",
    )

    assert [path for path in removed_paths if (ROOT / path).exists()] == []


def test_retired_product_state_routes_are_not_reintroduced() -> None:
    product_text = _combined(
        _production_files(
            "examples/medusa-agent/backend/medusa_agent",
            "examples/medusa-agent/backend/main.py",
            "examples/medusa-agent/frontend/src",
        )
    )
    retired_routes = (
        "/api/medusa-agent/state",
        "/api/medusa-agent/route-manifest",
        "/api/medusa-agent/projection",
        "/api/medusa-agent/route-stream",
        "/api/medusa-agent/action",
        "/api/medusa-agent/agent/stream",
        "/api/medusa-agent/inspect",
    )

    assert [route for route in retired_routes if route in product_text] == []
    assert PRODUCT_SPECIFIC_ROUTEDECK_ROUTE.search(product_text) is None


def test_product_runtime_has_no_phrase_router_or_synthetic_fallback_path() -> None:
    product_text = _combined(
        _production_files(
            "examples/medusa-agent/backend/medusa_agent",
            "examples/medusa-agent/frontend/src",
        )
    ).lower()
    forbidden = (
        "phrase_router",
        "alias_router",
        "command_router",
        "intent_map",
        "fake_catalog",
        "hardcoded product",
        "fallback assistant",
        "canned response",
        "mock fallback",
    )

    assert [term for term in forbidden if term in product_text] == []
