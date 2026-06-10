from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _all_text(paths: list[str]) -> str:
    return "\n".join(_read(path) for path in paths)


def test_routedeck_core_and_react_stay_product_neutral() -> None:
    paths = [
        *[str(path.relative_to(ROOT)) for path in (ROOT / "routedeck_core").glob("*.py")],
        *[str(path.relative_to(ROOT)) for path in (ROOT / "react" / "src").glob("*.ts")],
        *[str(path.relative_to(ROOT)) for path in (ROOT / "react" / "src").glob("*.tsx")],
    ]
    text = _all_text(paths).lower()

    forbidden = [
        "medusa",
        "product_ref",
        "variant_ref",
        "cart_ref",
        "line_ref",
        "/api/routedeck/medusa",
    ]
    assert [term for term in forbidden if term in text] == []


def test_medusa_frontend_uses_product_owned_read_only_projection() -> None:
    text = _all_text(
        [
            "examples/medusa-agent/frontend/src/App.tsx",
            "examples/medusa-agent/frontend/src/hooks/useRouteDeckProjection.ts",
        ]
    )

    assert "/api/medusa-agent/projection" in text
    assert 'data-testid="medusa-agent-workspace"' in text
    assert '"medusa-starter-message"' in text
    assert '"medusa-projected-surface"' in text
    assert '"route-map-graph"' in text
    assert "Projection-backed orientation" in text
    assert "setSelectedNodeId" in text
    assert "window.location.pathname" in text
    assert "surface_id" in text

    forbidden = [
        "surface_event",
        "product_ref",
        "variant_ref",
        "cart_ref",
        "/api/routedeck",
        "/api/medusa-agent/action",
        "/api/medusa-agent/inspect",
        "/api/medusa-agent/route-stream",
        "@medusajs",
        "Store API",
        "add to cart",
        "checkout",
        "admin",
    ]
    assert [term for term in forbidden if term in text] == []


def test_medusa_navgraph_is_read_only_and_home_centered() -> None:
    app_text = _read("examples/medusa-agent/frontend/src/App.tsx")
    route_map_source = app_text.split('data-testid="route-map-graph"', 1)[1].split('className="rail-note"', 1)[0]
    projection_text = _read("examples/medusa-agent/backend/services/routedeck_projection.py")

    assert "route-edge-home-browse" in route_map_source
    assert "route-edge-browse-detail" in route_map_source
    assert "route-edge-detail-cart" in route_map_source
    assert "<a " not in route_map_source
    assert "href=" not in route_map_source
    assert "window.location" not in route_map_source
    assert "history" not in route_map_source
    assert "sendMessage" not in route_map_source
    assert "setSelectedNodeId" in route_map_source
    assert 'id="home"' in projection_text
    assert "RouteDeckEdgeSpec(from_stage=\"home\"" in projection_text


def test_medusa_prompt_chips_remain_chat_prompts_not_route_operations() -> None:
    app_text = _read("examples/medusa-agent/frontend/src/App.tsx")

    prompt_source = app_text.split('data-testid="starter-chat-actions"', 1)[1].split("<form", 1)[0]

    assert "chatSuggestionsFromProjection" in app_text
    assert "projection?.presentation_state" in app_text
    assert "sendPrompt" in app_text
    assert "/api/medusa-agent/agent/stream" not in app_text
    assert 'data-testid="starter-chat-actions"' in app_text
    assert 'data-testid="medusa-chat-stream"' in app_text
    assert "legal_operations" not in prompt_source
    assert "operation_id" not in prompt_source
    assert "surface_event" not in prompt_source
    assert "RouteDeckOperation" not in prompt_source
    assert "MedusaProductDetailSurface" in app_text


def test_critical_prompt_blocks_navgraph_and_chip_drift() -> None:
    prompt = _read("critical_prompt.md")
    normalized_prompt = " ".join(prompt.split())

    assert "Visual navgraph surfaces are read-only orientation/inspection UI." in prompt
    assert "must not dispatch, navigate, mutate graph state, or change the browser URL." in normalized_prompt
    assert "Product action chips come from product-curated projected capabilities" in prompt
    assert "Product action chips belong to the product chat/assistant experience" in prompt
    assert "Agent-first reference apps should open with an assistant chat turn" in prompt
    assert "Internal `route.*` operations are never ordinary product chips." in prompt
    assert "Do not render `legal_operations` wholesale as chips." in prompt
    assert "Product surfaces and navgraph/inspector surfaces must stay separate." in prompt
    assert "the active product surface belongs inside the chat or workbench stream" in normalized_prompt
    assert "Address-bar deeplinks are product-owned URL codecs." in prompt
    assert "Do not make `?rd_node=...` the canonical public URL" in normalized_prompt
    assert "product chips render current-node no-op operations as ordinary next actions" in prompt
    assert "an agent reference app starts from an empty-state panel" in prompt
    assert "detached side panel instead of being embedded in the chat/workbench stream" in normalized_prompt
    assert "query-only `?rd_node=...` links as the canonical" in prompt


def test_reference_docs_block_surface_navgraph_chip_drift() -> None:
    reference = _read("docs/route-deck-reference.md")
    medusa = _read("docs/medusa-agent-reference-app.md")
    usage = _read("docs/using-routedeck.md")
    normalized_reference = " ".join(reference.split())
    normalized_medusa = " ".join(medusa.split())

    assert "`legal_operations` is a policy/runtime fact" in reference
    assert "Product surfaces and navgraph/inspector surfaces must be structurally separate" in reference
    assert "inside the chat or workbench stream, not as a detached product side panel" in reference
    assert "The Corpus pattern is the reference consumption model" in normalized_reference
    assert "New product examples should not make framework-looking query keys" in normalized_reference
    assert "Same-node operations are not ordinary next-action chips" in medusa
    assert "first visible Medusa agent state is an assistant chat turn" in medusa
    assert "Medusa product surface is embedded in the chat stream" in medusa
    assert "Product cards, home CTAs, variant buttons, and cart buttons emit" in normalized_medusa
    assert "the canonical visible deeplinks follow the Corpus path-owned codec pattern" in medusa
    assert "merging product surfaces with navgraph/inspector UI" in usage
    assert "making query-only `?rd_node=...` URLs the canonical public browser deeplinks" in usage


def test_medusa_canonical_deeplinks_are_path_based_with_legacy_query_decode() -> None:
    runtime_text = _read("examples/medusa-agent/backend/services/routedeck_projection.py")
    hook_text = _read("examples/medusa-agent/frontend/src/hooks/useRouteDeckProjection.ts")
    readme = _read("examples/medusa-agent/README.md")

    deeplink_source = runtime_text.split("def _deeplink_for_location", 1)[1].split("def _navgraph_for_location", 1)[0]
    decoder_source = hook_text.split("function projectionEndpointFromLocation", 1)[1]

    assert '"/detail/"' in runtime_text
    assert '"/browse"' in runtime_text
    assert '"/cart"' in runtime_text
    assert "rd_node" not in runtime_text
    assert "window.location.pathname" in decoder_source
    assert 'params.set("path"' in decoder_source
    assert 'params.set("surface_id"' in decoder_source
    assert "rd_node" not in decoder_source
    assert "The path remains the canonical public location" in " ".join(readme.split())
    assert "- `/detail/t-shirt`" in readme


def test_medusa_starts_with_assistant_turn_not_empty_state() -> None:
    app_text = _read("examples/medusa-agent/frontend/src/App.tsx")
    styles = _read("examples/medusa-agent/frontend/src/styles.css")

    assert '"medusa-starter-message"' in app_text
    assert 'className="starter-message"' in app_text
    assert "starter-chat-actions" in app_text
    assert 'className="empty-state"' not in app_text
    assert ".empty-state" not in styles


def test_medusa_projected_surfaces_are_embedded_and_read_only() -> None:
    app_text = _read("examples/medusa-agent/frontend/src/App.tsx")

    assert 'data-testid="medusa-agent-workspace"' in app_text
    assert 'data-testid="medusa-chat-stream"' in app_text
    assert 'data-testid="medusa-projected-surface"' in app_text
    assert "MedusaProductListSurface" in app_text
    assert "MedusaProductDetailSurface" in app_text
    assert "<AgentContextPanel" not in app_text
    assert "surface_event" not in app_text
    assert "add to cart" not in app_text.lower()


def test_medusa_runtime_keeps_private_refs_out_of_public_surface_props() -> None:
    runtime_text = _read("examples/medusa-agent/backend/services/routedeck_projection.py")

    assert 'DEFAULT_PRODUCT_HANDLE = "t-shirt"' in runtime_text
    assert '"product_handle": location.product_handle' in runtime_text
    for forbidden in [
        "product_ref",
        "variant_ref",
        "cart_ref",
        "prod_",
        "variant_",
        "cart_",
        "line_",
        "li_",
    ]:
        assert forbidden not in runtime_text


def test_medusa_implementation_has_no_product_specific_routedeck_route_or_phrase_router() -> None:
    paths = [
        *[str(path.relative_to(ROOT)) for path in (ROOT / "examples" / "medusa-agent" / "backend" / "routes").glob("*.py")],
        *[str(path.relative_to(ROOT)) for path in (ROOT / "examples" / "medusa-agent" / "backend" / "services").glob("*.py")],
        *[
            str(path.relative_to(ROOT))
            for path in (ROOT / "examples" / "medusa-agent" / "frontend" / "src").glob("*.tsx")
            if ".test." not in path.name
        ],
        *[str(path.relative_to(ROOT)) for path in (ROOT / "examples" / "medusa-agent" / "frontend" / "src" / "hooks").glob("*.ts")],
    ]
    text = _all_text(paths).lower()

    forbidden = [
        "/api/routedeck",
        "phrase_router",
        "alias_router",
        "command_router",
        "intent_map",
        "fake_catalog",
        "hardcoded product",
    ]
    assert [term for term in forbidden if term in text] == []
