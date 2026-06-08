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


def test_medusa_frontend_uses_surface_events_not_hidden_refs() -> None:
    text = _all_text(
        [
            "examples/medusa-agent/frontend/src/App.tsx",
            "examples/medusa-agent/frontend/src/hooks/useRouteDeckProjection.ts",
        ]
    )

    assert "surface_event" in text
    assert "product_ref" not in text
    assert "variant_ref" not in text
    assert "cart_ref" not in text
    assert "/api/routedeck" not in text


def test_medusa_navgraph_is_read_only_and_home_centered() -> None:
    app_text = _read("examples/medusa-agent/frontend/src/App.tsx")
    navgraph_source = app_text.split("function NavGraphView", 1)[1].split("function layoutNavGraphNodes", 1)[0]
    manifest_text = _read("examples/medusa-agent/backend/services/routedeck_manifest.py")

    assert "<a " not in navgraph_source
    assert "href=" not in navgraph_source
    assert "dispatch" not in navgraph_source.lower()
    assert '"home"' in manifest_text
    assert "id=\"home\"" in manifest_text or 'id="home"' in manifest_text
    assert "RouteDeckEdgeSpec(from_stage=\"home\"" in manifest_text


def test_medusa_action_chips_do_not_expose_hidden_route_operations() -> None:
    app_text = _read("examples/medusa-agent/frontend/src/App.tsx")
    chip_policy_source = app_text.split("function actionChipsForProjection", 1)[1].split("function CommerceSurface", 1)[0]
    chip_source = app_text.split("function ActionChips", 1)[1].split("function CommerceSurface", 1)[0]
    commerce_source = app_text.split("function CommerceSurface", 1)[1].split("function AgentContextPanel", 1)[0]
    agent_context_source = app_text.split("function AgentContextPanel", 1)[1].split("function NavGraphView", 1)[0]

    assert "route." in chip_policy_source
    assert "hidden" in chip_policy_source
    assert "execution_mode" in chip_policy_source
    assert "target_node" in chip_policy_source
    assert "currentNode" in chip_policy_source
    assert "NavGraphView" not in chip_policy_source
    assert "deeplink" not in chip_policy_source.lower()
    assert 'data-testid="medusa-chat-action-chips"' in chip_source
    assert 'data-testid="medusa-chat-stream"' in app_text
    assert "ActionChips" not in commerce_source
    assert "NavGraphView" not in commerce_source
    assert 'aria-label="Shopping surface"' in commerce_source
    assert "dispatchSurfaceEvent" in commerce_source
    assert 'aria-label="Agent context"' in agent_context_source
    assert "NavGraphView" in agent_context_source


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
    runtime_text = _read("examples/medusa-agent/backend/services/routedeck_runtime.py")
    hook_text = _read("examples/medusa-agent/frontend/src/hooks/useRouteDeckProjection.ts")
    readme = _read("examples/medusa-agent/README.md")

    deeplink_source = runtime_text.split("def _deeplink", 1)[1].split("def _public_cart_items", 1)[0]
    decoder_source = hook_text.split("function routeDeckParamsFromLocation", 1)[1]

    assert '"/detail/{product_path}"' in deeplink_source
    assert '"/browse"' in deeplink_source
    assert '"/cart"' in deeplink_source
    assert '"/?rd_node=' not in deeplink_source
    assert "pathSegments" in decoder_source
    assert 'routeDeckParams.set("rd_node", "home")' in decoder_source
    assert "legacyParams" in decoder_source
    assert "Legacy `?rd_node=...` links are" in readme
    assert "- `/detail/t-shirt`" in readme


def test_medusa_starts_with_assistant_turn_not_empty_state() -> None:
    app_text = _read("examples/medusa-agent/frontend/src/App.tsx")
    styles = _read("examples/medusa-agent/frontend/src/styles.css")

    assert 'data-testid="medusa-starter-message"' in app_text
    assert 'className="message-row assistant starter-message"' in app_text
    assert "starter-chat-actions" in app_text
    assert 'className="empty-state"' not in app_text
    assert ".empty-state" not in styles


def test_medusa_surface_is_embedded_in_chat_stream() -> None:
    app_text = _read("examples/medusa-agent/frontend/src/App.tsx")
    workspace_source = app_text.split('data-testid="medusa-agent-workspace"', 1)[1].split("<form", 1)[0]
    chat_source = workspace_source.split('data-testid="medusa-chat-stream"', 1)[1].split("<AgentContextPanel", 1)[0]

    assert "<CommerceSurface" in chat_source
    assert "<AgentContextPanel" not in chat_source
    assert workspace_source.index("<CommerceSurface") < workspace_source.index("<AgentContextPanel")


def test_medusa_runtime_keeps_private_refs_out_of_public_surface_props() -> None:
    runtime_text = _read("examples/medusa-agent/backend/services/routedeck_runtime.py")

    assert '"entity_key": self._entity_key("product", product.id)' in runtime_text
    assert '"entity_key": self._entity_key("variant", variant.id)' in runtime_text
    assert '"product_ref": self.product_refs.remember(product.id)' not in runtime_text
    assert '"variant_ref": self.variant_refs.remember(variant.id)' not in runtime_text
    assert '"cart_ref": state.cart_ref' not in runtime_text


def test_medusa_implementation_has_no_product_specific_routedeck_route_or_phrase_router() -> None:
    paths = [
        *[str(path.relative_to(ROOT)) for path in (ROOT / "examples" / "medusa-agent" / "backend" / "routes").glob("*.py")],
        *[str(path.relative_to(ROOT)) for path in (ROOT / "examples" / "medusa-agent" / "backend" / "services").glob("*.py")],
        *[str(path.relative_to(ROOT)) for path in (ROOT / "examples" / "medusa-agent" / "frontend" / "src").glob("*.tsx")],
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
