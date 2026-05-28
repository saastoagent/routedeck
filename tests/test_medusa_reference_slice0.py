import json
import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".md", ".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".toml"}
SKIP_DIRS = {".git", ".pytest_cache", "__pycache__", "node_modules", "dist", "build"}
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
    r"\b(must not|should not|do not|don't|wrong boundary|drift|appears|for example|not become|no product-specific)\b",
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
    assert "POST /api/medusa-agent/action" in text
    assert "POST /api/medusa-agent/agent/stream" in text
    assert "POST /api/medusa-agent/inspect" in text
    assert "GET /api/routedeck/manifest" in text
    assert "POST /api/routedeck/dispatch" in text
    assert re.search(r"separate from\s+the\s+product API", text)


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

    assert "RouteDeck API is allowed, expected, and encouraged" in medusa_spec
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
    assert "No RouteDeck runtime, manifest, projection, dispatch, inspect, or RouteDeck stream API is introduced in Slice 1." in plan
    assert "examples/medusa-agent/backend/app.py" in plan
    assert "examples/medusa-agent/frontend/src/App.tsx" in plan
    assert "python -m pytest examples/medusa-agent/backend/tests -q" in plan
    assert "npm test" in plan


def test_no_medusa_source_is_vendored_or_scaffolded_before_slice1():
    assert not (ROOT / "examples" / "medusa-agent").exists()

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
