import json
import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".md", ".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".toml"}
SKIP_DIRS = {".git", ".pytest_cache", "__pycache__", ".venv", "node_modules", "dist", "build"}
REFERENCE_SURFACE_ROOTS = ("README.md", "docs", "architecture")

MEDUSA_AGENT_ROUTEDECK_OWNERSHIP_PATTERNS = [
    re.compile(
        r"\bRouteDeck\b.{0,80}\b(hosts?|exposes?|owns?|hosting|exposing|owning)\b.{0,80}\bMedusa(?:\s+\w+){0,3}\s+agent\b",
        re.I,
    ),
    re.compile(
        r"\bRouteDeck[-\s]+(hosted|exposed|owned)\b.{0,80}\bMedusa(?:\s+\w+){0,3}\s+agent\b",
        re.I,
    ),
    re.compile(
        r"\bMedusa(?:\s+\w+){0,3}\s+agent\b.{0,80}\b(hosted|exposed|owned)\s+by\s+RouteDeck\b",
        re.I,
    ),
]

PRODUCT_SPECIFIC_ROUTEDECK_ROUTE = re.compile(
    r"/api/routedeck/(?:medusa|propertydesk|corpus|saastoagent|checkout|cart|order|payment|shipping|fulfillment)",
    re.I,
)

ALLOWED_PRODUCT_ROUTEDECK_PROHIBITION_CONTEXT = re.compile(
    r"\b(must not|should not|do not|don't|wrong boundary|drift|appears|for example|not become|"
    r"no(?:\s+`?/api/routedeck/|\s+product-specific)|not in|product-specific RouteDeck route|404)\b",
    re.I,
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _project_files(*roots: str):
    for root in roots:
        start = ROOT / root
        if start.is_file():
            yield start
            continue
        if not start.exists():
            continue
        for path in start.rglob("*"):
            if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
                continue
            if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
                continue
            yield path


def _combined_text(*roots: str) -> str:
    chunks = []
    for path in _project_files(*roots):
        chunks.append(f"\n--- {path.relative_to(ROOT).as_posix()} ---\n{_read(path)}")
    return "\n".join(chunks)


def _lines_with_context(path: Path):
    lines = _read(path).splitlines()
    for index, line in enumerate(lines):
        previous_line = lines[index - 1] if index > 0 else ""
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        yield index + 1, line, f"{previous_line}\n{line}\n{next_line}"


def test_medusa_reference_spec_is_active_source_of_truth():
    spec = ROOT / "docs" / "medusa-agent-reference-app.md"

    assert spec.exists(), "Slice 0 must create the active Medusa reference spec."

    text = _read(spec)
    assert "Status: active source of truth" in text
    assert "GET /api/medusa-agent/state" in text
    assert "GET /api/medusa-agent/route-manifest" in text
    assert "GET /api/medusa-agent/projection" in text
    assert "POST /api/medusa-agent/action" in text
    assert "POST /api/medusa-agent/agent/stream" in text
    assert "POST /api/medusa-agent/inspect" in text
    assert "No public Medusa example endpoint is served under `/api/routedeck/*`" in text
    assert "may be served under\n  `/api/routedeck/*`" not in text
    assert "RouteDeck contracts visible through product-owned" in " ".join(text.split())
    assert "Product action chips render in the Medusa chat/assistant experience" in text
    assert "Corpus quick-action pattern" in text


def test_medusa_slice_plans_require_chat_projection_convergence_and_grounding():
    critical_prompt = _read(ROOT / "critical_prompt.md")
    context = _read(ROOT / "context.md")
    code_map = _read(ROOT / "architecture" / "code-map.md")
    route_deck_reference = _read(ROOT / "docs" / "route-deck-reference.md")
    medusa_spec = _read(ROOT / "docs" / "medusa-agent-reference-app.md")
    micro_slices = _read(
        ROOT / "docs" / "superpowers" / "plans" / "2026-06-08-routedeck-medusa-micro-slices.md"
    )
    strategic_plan = _read(
        ROOT / "docs" / "superpowers" / "plans" / "2026-06-08-routedeck-open-source-medusa-agent.md"
    )
    normalized_route_deck_reference = " ".join(route_deck_reference.split())
    normalized_medusa_spec = " ".join(medusa_spec.split())
    normalized_micro_slices = " ".join(micro_slices.split())

    assert "Assistant prose alone is not a state update." in critical_prompt
    assert "Public chat must not invent product facts." in critical_prompt
    assert "2026-06-10 gap audit" in context
    assert "chat-to-projection convergence" in context
    assert "Medusa reference example" in code_map
    assert "chat-to-projection convergence" in code_map
    assert "Assistant prose without a matching projection/runtime update is drift." in normalized_route_deck_reference
    assert "Planning context is also the grounding boundary for public chat." in normalized_route_deck_reference
    assert "## Visible Surface Usability Gate" in medusa_spec
    assert "Assistant prose without a projection update is not accepted as completion." in normalized_medusa_spec
    assert "## Global Convergence And Grounding Gate" in micro_slices
    assert "Do not call it a usable agentic surface." in normalized_micro_slices
    assert "### Micro-Slice M3.7: Chat Can Invoke One Read Operation And Update Projection" in micro_slices
    assert "this is static orientation/projection proof, not a usable product-surface slice" in strategic_plan
    assert "Model-only catalog facts are drift." in strategic_plan


def test_propertydesk_is_not_described_as_flagship_reference_app():
    text = _combined_text("README.md", "docs", "architecture")

    assert not re.search(r"PropertyDesk.{0,100}flagship|flagship.{0,100}PropertyDesk", text, re.I | re.S)
    assert "docs/propertydesk-reference-app.md" in text
    assert "superseded" in _read(ROOT / "docs" / "propertydesk-reference-app.md").lower()


def test_route_deck_does_not_claim_to_host_expose_or_own_medusa_agent():
    failures = []

    for path in _project_files(*REFERENCE_SURFACE_ROOTS):
        for line_number, line, _context in _lines_with_context(path):
            if "described as" in line.lower():
                continue
            for pattern in MEDUSA_AGENT_ROUTEDECK_OWNERSHIP_PATTERNS:
                if pattern.search(line):
                    failures.append(f"{path.relative_to(ROOT).as_posix()}:{line_number}: {line.strip()}")
                    break

    assert not failures, "RouteDeck must not host, expose, or own the Medusa agent:\n" + "\n".join(failures)


def test_reference_surface_encourages_separate_routedeck_api_without_product_routes():
    medusa_spec = _read(ROOT / "docs" / "medusa-agent-reference-app.md")
    using_doc = _read(ROOT / "docs" / "using-routedeck.md")
    whitepaper = _read(ROOT / "docs" / "route-deck-whitepaper.md")

    assert "RouteDeck contracts visible through product-owned" in " ".join(medusa_spec.split())
    assert "No public Medusa example endpoint is served under `/api/routedeck/*`" in medusa_spec
    assert "RouteDeck can be exposed as a distinct generic API plane" in using_doc
    assert "Two API planes are valid, and they should stay distinct." in whitepaper
    assert "GET  /api/routedeck/manifest" in whitepaper
    assert "POST /api/<product>/agent/stream" in whitepaper

    failures = []

    for path in _project_files(*REFERENCE_SURFACE_ROOTS):
        for line_number, line, context in _lines_with_context(path):
            if "/api/routedeck/" not in line and "/api/routedeck/" not in context:
                continue
            if not PRODUCT_SPECIFIC_ROUTEDECK_ROUTE.search(context):
                continue
            if ALLOWED_PRODUCT_ROUTEDECK_PROHIBITION_CONTEXT.search(context):
                continue
            failures.append(f"{path.relative_to(ROOT).as_posix()}:{line_number}: {line.strip()}")

    assert not failures, "RouteDeck routes must stay generic, not product-specific:\n" + "\n".join(failures)


def test_routedeck_reference_is_the_unified_framework_authority():
    reference_path = ROOT / "docs" / "route-deck-reference.md"
    assert reference_path.exists()
    assert not (ROOT / "docs" / "route-deck-terms.md").exists()

    terms = _read(reference_path)
    assert "Status: canonical framework reference" in terms
    assert "Schema authority: `routedeck_core/models.py`" in terms

    for heading in [
        "## Core Vision",
        "## Truth And State Layers",
        "### Graph State",
        "### Projection",
        "### Component Local State",
        "### Surface Session State",
        "### Agent Context",
        "## Navgraph And Capability Contract",
        "### Navgraph",
        "### Capability",
        "### Operation",
        "### Legal Operation",
        "### Product Operation",
        "### Surface Intent",
        "### Available Entity",
        "### Rendered Entity",
        "### Selectable Entity",
        "### Planning Context",
        "## Surfaces",
        "### Surface",
        "### Surface Affordance",
        "### Generated Surface",
        "## Interaction Flows",
        "### Surface Interaction Event",
        "### Chat Capability Request",
        "### Semantic Observation",
        "### Agent Context Update",
        "## Topology And Runtime",
        "### Manifest",
        "### Node",
        "### Edge",
        "### Action Spec",
        "### Product Runtime",
        "### Runtime State",
        "### Dispatch",
        "### Navigation State",
        "### Internal Route Operation",
        "### RouteDeckStore",
        "## Diagnostics, Streams, And Boundaries",
        "### Diagnostics And Introspection",
        "### Events And Streams",
        "### Product Agent",
        "### Product Boundary",
    ]:
        assert heading in terms

    for schema_name in [
        "RouteDeckManifest",
        "RouteDeckNodeSpec",
        "RouteDeckEdgeSpec",
        "RouteDeckActionSpec",
        "RouteDeckRuntimeState",
        "RouteDeckProjection",
        "RouteDeckOperation",
        "RouteDeckDispatchInput",
        "RouteDeckDispatchResult",
        "RouteDeckSurface",
        "RouteDeckNavigationState",
        "RouteDeckIntrospection",
        "RouteDeckEvent",
        "RouteDeckLocation",
        "RouteDeckDeepLink",
    ]:
        assert schema_name in terms

    normalized_terms = " ".join(terms.split())
    for required_boundary in [
        "RouteDeck lets products and agents present dynamic UI without letting UI own application truth.",
        "Product graph truth -> RouteDeck navgraph -> capability contract -> RouteDeck projection",
        "RouteDeck exposes a navgraph that orients agents and users inside the product.",
        "navgraph is a graph: nodes are product-facing locations and edges are reachable routes between those locations.",
        "A visual surface that presents a navgraph must show that topology as a graph, not only as a flat list of labels.",
        "It is not necessarily the product graph.",
        "Visual navgraph surfaces are read-only orientation and inspection surfaces.",
        "must not dispatch, navigate, mutate graph state, or change the browser URL.",
        "navgraph node's deeplink is data for inspection and resume, not an `href` for the graph canvas.",
        "Action chips are separate product controls derived from product-curated capabilities, operations, affordances, or agent proposals.",
        "Action chips belong to the product chat or assistant experience.",
        "presented as product-agent suggestions, next-best actions, or composer-adjacent controls",
        "not as navgraph controls, graph-node actions, edge labels, or inspector controls.",
        "SaaStoAgent Corpus pattern",
        "The same action must be representable through chat planning context.",
        "must not be the source or rendering location for product action chips.",
        "not with the navgraph canvas or inspector.",
        "Internal `route.*` operations remain framework plumbing and must not appear as ordinary product action chips.",
        "State details such as reachable nodes, legal operations, capabilities, available entities, rendered entities, surface affordances, and edge action metadata belong in a read-only inspector or diagnostics layer.",
        "the product should expose a stable home or root navgraph node.",
        "Deeplinks are visible in the address bar",
        "RouteDeck defines the deeplink fields on `RouteDeckLocation` and `RouteDeckNavGraphNode`.",
        "Products own the URL format, route parsing, auth checks, tenancy checks, and state restoration.",
        "The Corpus pattern is the reference consumption model",
        "New product examples should not make framework-looking query keys",
        "A deeplink URL must be safe to show in the browser address bar.",
        "When the current RouteDeck location changes, the browser URL should track the current location's deeplink",
        "A visual navgraph must not use node deeplinks as clickable graph navigation.",
        "Navgraph answers the location question. Capability answers the action question.",
        "`graph_node` names the current RouteDeck/navgraph node",
        "Component local state does not enter planning context and does not update agent context.",
        "Surface session state is represented through projection props, `presentation_state`, or product runtime session state.",
        "`capability_id` connects manifest nodes and action specs to a shared ability",
        "Actions are not navgraph nodes.",
        "When a product action triggers a navgraph transition, the edge records that action in",
        "A RouteDeck node does not need to map one-to-one to a product graph node.",
        "The static RouteDeck contract for the product-facing navgraph and capability surface.",
        "A navgraph route declared as `RouteDeckEdgeSpec`.",
        '"can_back": true',
        "product-owned view derived from RouteDeck projection",
        "RouteDeck defines projection terms; the product owns prompt-ready summaries",
        "A surface presents runtime capabilities through declared affordances; it does not mutate graph state directly.",
        "Every semantic interaction that changes app state, agent state, or workflow position from a surface must also be available through product-agent planning context.",
        "Both this chat request and the surface event above resolve server-side to",
        "Available entities are the common entity pool for chat and surfaces",
        "Rendered entities are the subset a user can click, select, or inspect visually.",
        "Semantic observations are not raw UI logs.",
        "Raw UI events do not enter agent context.",
        "Text matching is a fallback for natural-language chat.",
        "RouteDeck does not own product prompts, model calls, LLM behavior",
        "Product integrations keep them hidden from ordinary",
        "semantic observation policy, URL/deeplink codecs, deeplink auth/resume policy, and domain side effects",
        '"available_entities"',
        '"surface_affordances"',
        '"capability_id": "cart.add_item"',
        '"entity_key": "variant:s-black"',
        '"surface_intent"',
        '"operation_id": "cart.add_item"',
        '"event_type": "guard_failure"',
    ]:
        assert required_boundary in normalized_terms

    assert re.search(r"\bmay\b|\bmaybe\b", terms, re.I) is None

    for doc in [
        "docs/agentic-ui-state-runtime.md",
        "docs/using-routedeck.md",
        "docs/route-deck-whitepaper.md",
        "docs/medusa-agent-reference-app.md",
    ]:
        text = _read(ROOT / doc)
        assert "docs/route-deck-reference.md" in text or "./route-deck-reference.md" in text
        assert "route-deck-terms.md" not in text


def test_whitepaper_names_product_owned_agent_and_public_reference_boundaries():
    text = _read(ROOT / "docs" / "route-deck-whitepaper.md")

    assert "agent execution, and agent streaming endpoints are product-owned" in text
    assert "are not RouteDeck operations" in text
    assert "Agent authority should be explicit" in text
    assert "Medusa is the future product-specific reference example" in text
    assert "SaaStoAgent should remain a case study and integration" in text
    assert "PropertyDesk should not be described as the active reference-app" in text
    assert "license metadata, third-party notices, package" in text


def test_print_friendly_whitepaper_matches_boundary_and_layout_direction():
    html = _read(ROOT / "docs" / "route-deck-whitepaper.html")

    assert "<table" not in html
    assert "<ul" not in html
    assert "Two API planes are valid, and they should stay distinct." in html
    assert "Product agents, agent execution, and agent streaming endpoints are product-owned" in html
    assert "GET  /api/routedeck/manifest" in html
    assert "POST /api/&lt;product&gt;/agent/stream" in html
    assert "Medusa becomes the future product-specific reference app" in html
    assert "SaaStoAgent should remain a case study and integration" in html
    assert "Raw public <code>/api/routedeck/*</code> routes are usually the wrong boundary" not in html
    assert "product state/action/stream APIs" not in html


def test_medusa_reference_defines_reset_fixture_rule():
    text = _read(ROOT / "docs" / "medusa-agent-reference-app.md")

    assert "## Reset Fixture Rule" in text
    assert "seeded local/demo Medusa fixture" in text
    assert "must restore the fixture to the seed state" in text
    assert "No slice may depend on production Medusa data" in text


def test_slice1_contract_is_decision_complete_for_next_plan():
    text = _read(ROOT / "docs" / "medusa-agent-reference-app.md")

    assert "### Slice 1 Implementation Contract" in text
    assert "`examples/medusa-agent/backend/app.py`" in text
    assert "`examples/medusa-agent/frontend/src/App.tsx`" in text
    assert "`POST /api/medusa-agent/agent/stream`" in text
    assert "`event: \"message_delta\"`" in text
    assert "text/event-stream" in text
    assert "LangGraph" in text
    assert "langgraph==1.2.2" in text
    assert "langchain-openai==1.2.2" in text
    assert "gpt-5-mini" in text
    assert "OPENAI_API_KEY" in text
    assert "stream_events" in text
    assert "configurable.thread_id" in text
    assert "`python -m pytest examples/medusa-agent/backend/tests -q`" in text
    assert "`npm test` from `examples/medusa-agent/frontend`" in text


def test_slice1_plan_document_is_linked_and_decision_complete():
    spec_text = _read(ROOT / "docs" / "medusa-agent-reference-app.md")
    plan_path = ROOT / "docs" / "superpowers" / "plans" / "2026-05-28-medusa-agent-slice1.md"

    assert "docs/superpowers/plans/2026-05-28-medusa-agent-slice1.md" in spec_text
    assert plan_path.exists()

    plan = _read(plan_path)
    assert "# Medusa Agent Slice 1 Implementation Plan" in plan
    assert "Use superpowers:subagent-driven-development" in plan
    assert "foundation-agent" in plan
    assert "text/event-stream" in plan
    assert "LangGraph" in plan
    assert "langgraph==1.2.2" in plan
    assert "langchain-openai==1.2.2" in plan
    assert "fastapi==0.136.3" in plan
    assert "\"vite\": \"8.0.14\"" in plan
    assert "\"react\": \"19.2.6\"" in plan
    assert "gpt-5-mini" in plan
    assert "OPENAI_API_KEY" in plan
    assert "stream_events" in plan
    assert "InMemorySaver" in plan
    assert "configurable.thread_id" in plan
    assert "Active state-stream contract after M3.7: `GET /api/medusa-agent/route-stream`" in plan
    assert "`POST /api/medusa-agent/agent/stream` must not emit `projection_update`" in plan
    assert "Navgraph renderer: a visible navgraph is a literal node/edge graph." in plan
    assert "examples/medusa-agent/backend/app.py" in plan
    assert "examples/medusa-agent/frontend/src/App.tsx" in plan
    assert "python -m pytest examples/medusa-agent/backend/tests -q" in plan
    assert "npm test" in plan


def test_medusa_runnable_example_keeps_transport_separate_from_buyer_specs():
    example = ROOT / "examples" / "medusa-agent"
    assert example.exists()

    implementation_failures = []
    disallowed_product_patterns = [
        PRODUCT_SPECIFIC_ROUTEDECK_ROUTE,
        re.compile(r"@routedeck/react", re.I),
        re.compile(r"@medusajs/", re.I),
        re.compile(r"/api/medusa-agent/(?:state|route-manifest|route-snapshot|action|inspect)", re.I),
        re.compile(r"\bsurface_event\b", re.I),
    ]

    production_chunks = []
    for path in _project_files("examples/medusa-agent/backend", "examples/medusa-agent/frontend/src"):
        relative_parts = path.relative_to(ROOT).parts
        if "tests" in relative_parts or ".test." in path.name:
            continue
        text = _read(path)
        production_chunks.append(text)
        for pattern in disallowed_product_patterns:
            if pattern.search(text):
                implementation_failures.append(
                    f"{path.relative_to(ROOT).as_posix()}: {pattern.pattern}"
                )

    assert not implementation_failures, (
        "The runnable Medusa example must not reintroduce retired product-specific RouteDeck APIs or direct Medusa SDK coupling:\n"
        + "\n".join(implementation_failures)
    )

    spec_text = _combined_text(
        "examples/medusa-agent/backend/medusa_agent/composition.py",
        "examples/medusa-agent/backend/medusa_agent/features",
    ).lower()
    for required in [
        "buyer.home",
        "catalog.browse",
        "catalog.product",
        "cart.summary",
        "checkout.review",
        "orders.confirmation",
        "checkout.place_order",
    ]:
        assert required in spec_text
    for banned in [
        "routedeckruntimebase",
        "build_route_deck_state_graph",
        "medusastoreclient",
        "httpx",
        "/store/",
        "/admin/",
    ]:
        assert banned not in spec_text

    implementation_text = "\n".join(production_chunks)
    assert "/api/medusa-agent/agent/stream" in implementation_text
    assert "/api/medusa-agent/projection" in implementation_text
    assert "/api/medusa-agent/route-stream" in implementation_text
    assert "text/event-stream" in implementation_text
    assert "configurable" in implementation_text
    assert "thread_id" in implementation_text
    assert "/api/routedeck" not in implementation_text.lower()

    public_text = _combined_text(
            "examples/medusa-agent/frontend/src/App.tsx",
            "examples/medusa-agent/frontend/src/hooks/useSSEChat.ts",
            "examples/medusa-agent/frontend/src/hooks/useRouteDeckEvents.ts",
            "examples/medusa-agent/frontend/src/hooks/useRouteDeckProjection.ts",
            "examples/medusa-agent/frontend/src/styles.css",
        ).lower()
    for required in [
        "route map",
        "inspector",
        "projection-backed orientation",
        "surface_id",
        "start with normal shopping chat",
        "/api/medusa-agent/projection",
        "/api/medusa-agent/route-stream",
        "@xyflow/react",
    ]:
        assert required in public_text

    for banned in [
        "surface_event",
        "operation_id",
        "/api/medusa-agent/action",
        "/api/routedeck",
        "checkout",
        "payment",
        "shipping",
        "fulfillment",
        "admin",
        "add to cart",
        "catalog.",
        "cart.add_item",
        "cart.create",
        "cart.view",
    ]:
        assert banned not in public_text

    for private_prefix in ["prod_", "variant_private", "cart_private", "line_private", "product_ref", "variant_ref", "cart_ref"]:
        assert private_prefix not in public_text

    package_text = _combined_text("routedeck_core", "routedeck_langgraph", "react/src")
    assert "medusa" not in package_text.lower()


def test_public_readiness_license_metadata_exists():
    assert "MIT License" in _read(ROOT / "LICENSE")
    assert (ROOT / "THIRD_PARTY_NOTICES.md").exists()

    pyproject = tomllib.loads(_read(ROOT / "pyproject.toml"))
    assert pyproject["project"]["license"] == "MIT"
    assert "License :: OSI Approved :: MIT License" in pyproject["project"]["classifiers"]
    assert pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["license-files"] == ["LICENSE"]

    package = json.loads(_read(ROOT / "react" / "package.json"))
    assert package["license"] == "MIT"
