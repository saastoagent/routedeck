# RouteDeck And Medusa Buyer Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and verify a clean RouteDeck framework plus a standalone Medusa guest-buyer agent that completes the real local flow from product discovery through a verified order confirmation.

**Architecture:** RouteDeck is a product-neutral interaction-state framework with immutable feature specifications, runtime bindings, one supervised operation runner, durable SQLite session state, generic FastAPI/SSE transport, and headless/React frontend packages. The Medusa application is the first consumer: it owns typed Store API access, commerce handlers/providers/guards, LangGraph prompt/model behavior, and product surfaces. Work proceeds in consumer-driven vertical slices so a framework-only test never completes a task.

**Tech Stack:** Python 3.11.9, Pydantic 2, FastAPI, httpx, LangGraph/LangChain, SQLite, cryptography, pytest, mypy, Ruff, React 19, TypeScript, Vite, Vitest, Playwright, pnpm workspaces, Docker Compose, Medusa 2.13.6, PostgreSQL 16, Redis 7, and Medusa `pp_system_default` as the visibly labeled system/manual demo provider.

## Global Constraints

- Execute on the local Windows machine only. Do not probe or fall back to the Mac mini.
- Work on the existing `saastoagent` branch. Stage explicit paths only; the repository has extensive unrelated deletions and untracked research files.
- Use a fresh `.venv` from the RouteDeck project root. Do not rely on globally installed LangGraph/FastAPI packages.
- Use bundled Node `v24.14.0` and pnpm `11.7.0` for frontend work; declare Node `>=22.12.0` in package metadata.
- RouteDeck runtime product paths contain no fixtures, synthetic data, canned assistant responses, phrase routers, regex intent routing, hidden fallbacks, or default handlers.
- Test doubles and deterministic scripted models live only under explicitly named test packages.
- The only product data path is the real dedicated local Medusa demo stack. Missing Store API data or credentials fails visibly.
- RouteDeck core imports no LangGraph, FastAPI, React, Medusa, httpx, SQLite adapter, or product module.
- Medusa endpoint templates and HTTP transport exist only in `examples/medusa-agent/backend/medusa_agent/medusa/client/http.py`.
- The Medusa frontend makes zero direct `/store/*` calls; UI and agent actions use the same `RouteDeckOperationRunner` path.
- RouteDeck owns durable session, conversation, navigation, review, operation, projection, and event state. Medusa remains authoritative for commerce records.
- External writes are never automatically retried. Only typed `not_sent` evidence permits a fresh proposal; ambiguous writes become `external_outcome_unknown`.
- `checkout.place_order` is reviewed, invokes complete-cart once, and reaches confirmation only after `type: "order"` plus an independent order re-read.
- Checkout email/address fields use the encrypted private-form channel and never enter public projection, ordinary SSE, model context, URLs, or logs.
- The SQLite reference adapter supports one live application instance and enforces a fenced instance lease, CAS writes, short transactions, and durable replay.
- Each task follows RED -> verify failure -> minimal GREEN -> focused regression -> commit -> push. Do not use `git add -A`.
- The accepted design at `docs/superpowers/specs/2026-07-11-routedeck-medusa-agent-design.md` is authoritative when older RouteDeck documents conflict.

---

## Local Setup

Run once from `agent-lab-powered-projects/routedeck` before Task 1 source work:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e . pytest
$env:PATH="C:\Users\ragha\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin;C:\Users\ragha\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\fallback;$env:PATH"
node --version
pnpm --version
```

Expected versions: Python `3.11.9`, Node `v24.14.0`, pnpm `11.7.0`. The initial editable install intentionally uses only dependencies that exist before Task 2; Task 2 installs the new extras immediately after declaring them. Do not start services during setup. Task 11 is the first task authorized to start the dedicated Medusa integration stack.

## Commit Safety Protocol

The repository is broadly dirty outside this project. Before editing each task, inspect every path in that task's **Files** section and stop on any pre-existing overlap. The Git index must be empty before task staging; do not disturb user-owned staged state.

After verification, manually construct `$taskFiles` as the exact repository-relative file paths changed by that task, expanding every brace/directory entry in **Files** to individual files. Do not populate it automatically from a directory, glob, `git status`, or broad pathspec. Deleted files are listed individually. Then run this PowerShell gate from the RouteDeck project root:

```powershell
function Invoke-VerifiedTaskStage([string[]] $TaskFiles) {
    if (-not $TaskFiles -or $TaskFiles.Count -eq 0) { throw "Task file allowlist is empty" }
    if (@(git diff --cached --name-only).Count -ne 0) { throw "Git index was not empty" }

    $expected = @($TaskFiles | ForEach-Object { $_.Replace("\", "/") } | Sort-Object -Unique)
    foreach ($path in $expected) {
        if (Test-Path -LiteralPath $path -PathType Container) {
            throw "Directory staging is forbidden: $path"
        }
    }

    git add -- $expected
    if ($LASTEXITCODE -ne 0) { throw "git add failed" }

    $staged = @(git diff --cached --name-only | Sort-Object -Unique)
    $mismatch = @(Compare-Object -ReferenceObject $expected -DifferenceObject $staged)
    if ($mismatch.Count -ne 0) { throw "Staged paths differ from the task allowlist: $mismatch" }

    git diff --cached --check
    if ($LASTEXITCODE -ne 0) { throw "Staged diff check failed" }
    git diff --cached --stat
}
```

Every task's commit block invokes `Invoke-VerifiedTaskStage -TaskFiles $taskFiles` only after the exact array has been reviewed. A commit is forbidden if the cached path list differs by even one file. No task uses `git add -A`, `.`, a directory operand, or an inferred changed-file list.

## Target File Map

### Python framework

```text
routedeck_core/
  app/{feature,bindings,compiler,compiled}.py
  contracts/{application,operations,navigation,surfaces,projection,session,events,conversation,failures,retention}.py
  state/{session,reducer,history,leases}.py
  context/{providers,scope}.py
  supervision/{runner,guards,reviews,outcomes}.py
  navigation/{engine,routes,deep_links}.py
  projection/{projector,redaction}.py
  ports/{executor,session_store,clock,notifier}.py
  errors.py

routedeck_langgraph/{middleware,tool_wrapper,model_context}.py
routedeck_fastapi/{router,sse,dependencies}.py
routedeck_sqlite/{store,schema,migrations,codec,connection,instance_lease}.py
routedeck_testing/{conformance,factories,scripted_model}.py
```

The existing flat modules remain temporary compatibility facades for Corpus imports. The fresh Medusa application may not import `RouteDeckRuntimeBase`, `RouteDeckManifestBuilder`, or `build_route_deck_state_graph`.

### Frontend framework

```text
package.json
pnpm-workspace.yaml
tsconfig.base.json
vitest.workspace.ts
packages/core/src/{contracts,client,store,routing,private-forms}/
packages/react/src/{provider,hooks,surfaces,navigation,private-forms,review,status,inspector}/
packages/testing/src/
```

`@routedeck/core` is headless and has no React dependency. `@routedeck/react` contains bindings and framework UI primitives. `@routedeck/testing` contains test-only harnesses. The old `react/` directory is removed only after its useful store, history, topology, and edge-routing behavior is migrated and all new package tests pass.

### Medusa application

```text
examples/medusa-agent/
  backend/
    pyproject.toml
    main.py
    medusa_agent/
      config.py
      composition.py
      agent.py
      api/{chat,health}.py
      medusa/client/{protocol,http,models,errors}.py
      features/catalog/{feature,models,providers,handlers}.py
      features/cart/{feature,models,providers,guards,handlers}.py
      features/checkout/{feature,models,providers,guards,handlers}.py
      features/orders/{feature,models,providers,handlers}.py
  frontend/src/
    app/
    routedeck/
    features/{catalog,cart,checkout,orders}/
    ui/
  infra/{compose.yaml,demo-manifest.json,medusa-setup.sh,medusa-sentinel.ts,seed-fingerprint.ts}
  scripts/{demo-stack.ps1,release-verify.ps1}
  e2e/
```

### Validation and documentation

```text
tests/{app,state,navigation,supervision,projection,sqlite,events,fastapi,langgraph,conformance}/
scripts/{export_contracts.py,check_boundaries.py,check_critical_coverage.py}
artifacts/release/<utc-run-id>/
decisions/ADR-004-routedeck-medusa-consumer-driven-runtime.md
```

## Shared Test Interfaces

Test snippets below use only these named helpers. They are real test-only APIs, not product fallbacks, and must be implemented before the first task that consumes them.

### Python framework test support

`routedeck_testing/factories.py` defines:

```python
def session_factory(*, contact_email: str | None = None) -> RouteDeckSession: ...
def operation_request(
    *,
    operation_id: str = "cart.add_item",
    entity_key: str = "variant_1",
    source: OperationSource = OperationSource.SURFACE,
    request_id: str = "request-1",
    expected_session_version: int = 1,
) -> OperationRequest: ...
def place_order_request(*, request_id: str) -> OperationRequest: ...
def chat_turn_claim(*, request_id: str, expected_session_version: int = 1) -> TurnClaim: ...
def invalid_app(mutation: str) -> RouteDeckAppSpec: ...
def next_session(snapshot: SessionSnapshot) -> RouteDeckSession: ...
def capability_for_other_session() -> ResumeCapability: ...
def finalized_turns(*, user: str, assistant: str) -> tuple[FinalizedConversationTurn, ...]: ...
def turn_interrupted_failure() -> RouteDeckFailure: ...
async def persist_finalized_turn(
    store: RouteDeckSessionStore, *, user_text: str, assistant_text: str,
) -> SessionSnapshot: ...

class RecordingExecutor(OperationExecutor):
    calls: list[OperationInvocation]

class RecordingNotifier(RouteDeckNotifier):
    events: list[RouteDeckEvent]

class SecretRaisingExecutor(OperationExecutor):
    async def execute(self, *args, **kwargs):
        raise RuntimeError("secret-token-in-exception")
```

`tests/conftest.py` provides `database_path`, `codec`, `store`, `runtime`, `runner`, `runner_factory`, and generic FastAPI `client` fixtures. `tests/events/support.py` provides `parse_sse()` and `take_sse_frames()`. `tests/langgraph/support.py` provides `session_at()`, `model_request()`, `all_product_tools()`, `place_order_tool_call()`, `wrapper()`, `make_raw_graph()`, and `graph_edges()`. These helpers construct public contracts and invoke the actual reducer, runner, middleware, and transport; they contain no alternate business behavior. Each fixture creates isolated temporary state and closes it after the test.

### Medusa backend test support

`examples/medusa-agent/backend/tests/support/medusa.py` defines `StubMedusaStoreClient`, `CountingMedusaStoreClient`, `RecordingMedusaStoreClient`, `RecordingTransport`, `settings()`, `buyer_market()`, `product()`, `variant()`, `checkout_contact()`, `shipping_option()`, `provider()`, `order_result()`, `order()`, and `order_item()`. The recording clients implement the full `MedusaStoreClient` protocol, reject unstubbed calls, and expose typed call records. Values returned by `settings()` and the model factories are explicit unit-test data and never imported by product modules.

`examples/medusa-agent/backend/tests/support/runtime.py` defines `build_test_medusa_runtime()`, `app_with()`, `run_catalog_list()`, `dispatch()`, `initialize_buyer_session()`, `add_item()`, `save_contact()`, `load_shipping_options()`, `enter_payment()`, `propose_place_order()`, `reject()`, `mutate_cart_total()`, `accept()`, `approve_place_order()`, `run_scripted_buyer_until_review()`, `projection_json()`, `event_json()`, `model_context_json()`, and `chat()`. Each is a thin arrangement/invocation helper over the production composition and shared runner; none contains assertions, routing rules, fallback behavior, or product results.

`examples/medusa-agent/backend/tests/conftest.py` provides the Medusa-composed `medusa_runtime`, `runner`, `client`, `private_forms`, `store`, `session_id`, compiled `app`, and temporary persistent-store fixtures. `examples/medusa-agent/backend/tests/integration/real_medusa/conftest.py` is the only fixture layer allowed to load the generated real demo manifest and credentials.

`routedeck_testing/scripted_model.py` defines `ScriptedToolModel`, `ScriptedTextModel`, and `tool_call()` for deterministic test-only LangGraph turns. Product modules accept an injected model and never import these types.

### Frontend and browser test support

`packages/testing/src/componentHarness.tsx` defines `storeAt()` and `renderHost()`. `examples/medusa-agent/frontend/src/tests/support/buyer.tsx` defines `renderBuyer()` and `projectionWithProducts()`. `examples/medusa-agent/e2e/support/buyer-flow.ts` defines `fillPrivateContact()` and `runBuyerFlow()`. All frontend helpers receive explicit snapshots or live page handles; none fabricate product data inside product code.

### Task 1: Promote The Approved Design To Active Authority

**Files:**
- Create: `decisions/ADR-004-routedeck-medusa-consumer-driven-runtime.md`
- Create: `tests/test_active_design_authority.py`
- Modify: `decisions/README.md`
- Modify: `context.md`
- Modify: `critical_prompt.md`
- Modify: `architecture/code-map.md`
- Modify: `test_index/README.md`

**Interfaces:**
- Consumes: approved design specification and the user's permanent local-runtime decision.
- Produces: one unambiguous active authority chain: ADR-004 -> design spec -> this plan.

- [ ] **Step 1: Write the failing authority test**

```python
from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_active_context_authorizes_the_medusa_runtime() -> None:
    context = (ROOT / "context.md").read_text(encoding="utf-8")
    decisions = (ROOT / "decisions" / "README.md").read_text(encoding="utf-8")
    assert "ADR-004-routedeck-medusa-consumer-driven-runtime.md" in context
    assert "ADR-004-routedeck-medusa-consumer-driven-runtime.md" in decisions
    assert "No replacement implementation plan is active" not in context
    assert "ask whether to use local, Mac mini" not in context


def test_retired_gate_is_not_current_authority() -> None:
    prompt = (ROOT / "critical_prompt.md").read_text(encoding="utf-8")
    assert "ADR-004" in prompt
    assert "new SQLite/event/outbox durability" not in prompt
    assert "independent example projects" not in prompt
```

- [ ] **Step 2: Run the authority test and verify RED**

Run: `python -m pytest tests/test_active_design_authority.py -q`

Expected: FAIL because current context still points to ADR-003 and defers SQLite/Medusa.

- [ ] **Step 3: Write ADR-004 and update authority documents**

ADR-004 must state, without duplicating the entire design:

```markdown
# ADR-004: RouteDeck And Medusa Advance Through Consumer-Driven Runtime Slices

Status: Accepted
Date: 2026-07-11

ADR-004 preserves ADR-003's interaction-governance identity and supersedes its
Corpus-first sequencing and explicit deferrals. The approved Medusa buyer-agent
design authorizes feature-composed authoring, durable RouteDeck state, generic
FastAPI/SSE and SQLite adapters, optional LangGraph middleware, and the
standalone Medusa portability proof. Product handlers still execute through an
injected host executor; RouteDeck contains no Medusa business logic.
```

The plan commit has already changed the design status to `Approved; implementation plan active`; verify that wording remains intact. Make `context.md`, `critical_prompt.md`, the decision index, code map, and test index point to ADR-004 and local-only execution. Retain ADR-003 as historical rationale.

- [ ] **Step 4: Run authority and documentation checks**

Run:

```powershell
python -m pytest tests/test_active_design_authority.py -q
python scripts/check_doc_coverage.py
```

Expected: authority test PASS; doc coverage produces no blocking missing-owner finding for the changed files.

- [ ] **Step 5: Commit and push Task 1**

```powershell
Invoke-VerifiedTaskStage -TaskFiles $taskFiles
git commit -m "docs: activate RouteDeck Medusa runtime design"
git push origin saastoagent
```

### Task 2: Establish Python Package And Failure Boundaries

**Files:**
- Modify: `pyproject.toml`
- Modify: `routedeck_core/__init__.py`
- Create: `routedeck_core/contracts/failures.py`
- Create: `routedeck_core/errors.py` as a compatibility re-export
- Create: package `__init__.py` and `py.typed` files from the target map except the colliding `routedeck_core/app/` and `routedeck_core/navigation/` packages, which Task 3 migrates explicitly from the current `app.py` and `navigation.py` modules
- Create: `tests/test_public_api.py`
- Create: `tests/test_boundary_rules.py`
- Create: `scripts/check_boundaries.py`
- Create: `examples/medusa-agent/backend/pyproject.toml`
- Create: `examples/medusa-agent/backend/medusa_agent/__init__.py`
- Create: `examples/medusa-agent/backend/medusa_agent/composition.py`
- Create: `examples/medusa-agent/backend/tests/contract/test_framework_imports.py`

**Interfaces:**
- Consumes: ADR-004 package boundary.
- Produces: `RouteDeckFailure`, adapter package imports, an executable dependency boundary report, and a Medusa composition root that imports public packages without internal-path coupling.

- [ ] **Step 1: Create failing package and boundary tests**

```python
def test_public_packages_import() -> None:
    import routedeck_core
    import routedeck_fastapi
    import routedeck_langgraph
    import routedeck_sqlite
    import routedeck_testing

    assert routedeck_core.RouteDeckFailure.__name__ == "RouteDeckFailure"


def test_core_has_no_adapter_or_product_imports() -> None:
    from scripts.check_boundaries import scan_python_imports

    violations = scan_python_imports(
        package="routedeck_core",
        forbidden=(
            "fastapi", "langgraph", "langchain", "httpx", "sqlite3", "medusa_agent",
            "routedeck_fastapi", "routedeck_langgraph", "routedeck_sqlite",
        ),
    )
    assert violations == []


def test_medusa_composition_uses_only_public_routedeck_packages() -> None:
    from medusa_agent.composition import framework_packages

    assert framework_packages() == (
        "routedeck_core", "routedeck_fastapi", "routedeck_langgraph", "routedeck_sqlite"
    )
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `python -m pytest tests/test_public_api.py tests/test_boundary_rules.py -q`

Expected: FAIL because adapter packages and the typed failure contract do not exist.

- [ ] **Step 3: Add package metadata and the failure contract**

Use explicit extras in `pyproject.toml`:

```toml
[project.optional-dependencies]
langgraph = ["langgraph==1.2.2", "langchain==1.2.2", "langchain-openai==1.2.2"]
fastapi = ["fastapi==0.136.3", "httpx==0.28.1", "uvicorn==0.48.0"]
sqlite = ["cryptography>=43,<47"]
testing = ["pytest==9.0.3", "pytest-asyncio==1.4.0", "pytest-cov>=6,<8"]
dev = ["build>=1.2,<2", "mypy>=1.14,<2", "ruff>=0.9,<1"]

[tool.hatch.build.targets.wheel]
packages = [
  "routedeck_core",
  "routedeck_langgraph",
  "routedeck_fastapi",
  "routedeck_sqlite",
  "routedeck_testing",
]
```

Create the stable core error model in `routedeck_core/contracts/failures.py`; `routedeck_core/errors.py` and the root public API re-export it without defining a second model:

```python
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FailureKind(StrEnum):
    CONTRACT = "contract"
    STATE_CONFLICT = "state_conflict"
    CONTEXT_PROVIDER = "context_provider"
    GUARD = "guard"
    REVIEW = "review"
    TRANSPORT = "transport"
    PROVIDER_PROTOCOL = "provider_protocol"
    BUSINESS = "business"
    PERSISTENCE = "persistence"
    EXTERNAL_OUTCOME_UNKNOWN = "external_outcome_unknown"
    INTERNAL = "internal"


class FailureSafeDetails(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    affected_capability: str | None = None
    provider: str | None = None
    provider_code: str | None = None
    http_status: int | None = Field(default=None, ge=100, le=599)
    delivery_phase: Literal["not_sent", "possibly_sent", "response_received"] | None = None


class RouteDeckFailure(BaseModel):
    model_config = ConfigDict(frozen=True)
    kind: FailureKind
    code: str
    phase: str
    correlation_id: str
    operation_id: str | None = None
    request_id: str | None = None
    public_message: str
    recovery_directive: str | None = None
    safe_details: FailureSafeDetails = Field(default_factory=FailureSafeDetails)
```

`FailureSafeDetails` is the complete persistence/projection allowlist. Failure constructors accept stable codes and the typed fields above, never raw exceptions, exception chains, request/response bodies, headers, arguments, or arbitrary dictionaries. Adapter classifiers may inspect exception classes and structured status/code fields transiently, but discard raw text before constructing a failure.

Add the negative contract test:

```python
def test_failure_details_reject_raw_diagnostics() -> None:
    with pytest.raises(ValidationError):
        FailureSafeDetails.model_validate({"response_body": "secret", "exception": "token"})
```

`routedeck_core.__init__` exports only intentional contracts and no runtime subclass. Add a minimal Medusa `composition.py` that imports those public packages and exposes no business behavior yet; its contract test is the consumer proof for this package slice.

Create the example backend as an installable package now so all later tests and CLI exports use ordinary imports rather than `PYTHONPATH` mutation:

```toml
[project]
name = "routedeck-medusa-agent-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["routedeck-core"]

[tool.hatch.build.targets.wheel]
packages = ["medusa_agent"]
```

- [ ] **Step 4: Implement the AST import checker and run GREEN**

`scan_python_imports` must parse `ast.Import` and `ast.ImportFrom`, match both an exact forbidden module and its dotted descendants, return stable `path:line:module` strings, and never infer from comments or string literals.

Run:

```powershell
python -m pip install -e ".[langgraph,fastapi,sqlite,testing,dev]" -e .\examples\medusa-agent\backend
python -m pytest tests/test_public_api.py tests/test_boundary_rules.py examples/medusa-agent/backend/tests/contract/test_framework_imports.py -q
python scripts/check_boundaries.py --json artifacts/boundary-bootstrap.json
python -m build
```

Expected: PASS; wheel contains all five packages; boundary report has zero core violations.

- [ ] **Step 5: Commit and push Task 2**

```powershell
Invoke-VerifiedTaskStage -TaskFiles $taskFiles
git commit -m "feat: establish RouteDeck package boundaries"
git push origin saastoagent
```

### Task 3: Compile Feature Specifications And The Medusa Buyer Graph

**Files:**
- Remove after compatibility behavior is migrated: `routedeck_core/app.py`
- Remove after compatibility behavior is migrated: `routedeck_core/navigation.py`
- Create: `routedeck_core/app/__init__.py` as the compatibility/public package facade
- Create: `routedeck_core/navigation/__init__.py` as the compatibility/public package facade
- Create: `routedeck_core/contracts/{application,operations,navigation,surfaces}.py`
- Create: `routedeck_core/app/{feature,bindings,compiler,compiled}.py`
- Create: `routedeck_core/navigation/routes.py`
- Create: `routedeck_testing/factories.py` with compiler-invalid-spec factories
- Create: `tests/app/{test_feature_compiler,test_app_composition,test_compiled_contract,test_route_compiler}.py`
- Create: `examples/medusa-agent/backend/medusa_agent/features/{catalog,cart,checkout,orders}/feature.py`
- Create: `examples/medusa-agent/backend/medusa_agent/features/__init__.py` and each feature package `__init__.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/composition.py`
- Create: `scripts/export_contracts.py`

**Interfaces:**
- Consumes: `RouteDeckFailure` and the nine-node approved buyer flow.
- Produces: `FeatureSpec`, `FeatureBindings`, `CompiledRouteDeckApp`, typed object references, validated route templates, executable test paths, and the frontend contract JSON.

- [ ] **Step 1: Write compiler tests for valid and invalid applications**

```python
def test_medusa_features_compile_to_the_nine_node_graph() -> None:
    app = compile_medusa_app_spec()
    assert tuple(node.id for node in app.spec.nodes) == (
        "buyer.home", "catalog.browse", "catalog.product", "cart.summary",
        "checkout.contact", "checkout.delivery", "checkout.payment",
        "checkout.review", "orders.confirmation",
    )
    assert app.routes.encode("catalog.product", {"product_handle": "t-shirt"}) == "/products/t-shirt"
    assert app.frontend_contract.surfaces["catalog.product_detail"].component == "catalog.product_detail"


@pytest.mark.parametrize("mutation", [
    "duplicate_node", "duplicate_route", "dangling_transition", "missing_surface",
    "missing_outcome", "missing_provider", "unreachable_node", "hierarchy_cycle",
])
def test_compiler_rejects_invalid_specs(mutation: str) -> None:
    with pytest.raises(RouteDeckValidationError):
        compile_app(invalid_app(mutation))
```

- [ ] **Step 2: Run compiler tests and verify RED**

Run: `python -m pytest tests/app -q`

Expected: collection/import failure because the feature compiler does not exist.

- [ ] **Step 3: Implement immutable specification and binding planes**

The central contracts are frozen Pydantic models and object references:

```python
class OperationSpec(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    input_schema: dict[str, Any]
    safety_class: SafetyClass
    review_policy: ReviewPolicy = ReviewPolicy.NONE
    outcomes: tuple[str, ...]


class NodeSpec(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    title: str
    kind: NodeKind
    parent: NodeRef | None = None
    route: RouteSpec
    context_providers: tuple[ContextProviderSpec, ...]
    entity_providers: tuple[EntityProviderSpec, ...]
    operations: tuple[OperationSpec, ...]
    capabilities: tuple[CapabilitySpec, ...]
    surfaces: SurfaceSlotsSpec
    navigation: NavigationPolicySpec
    recovery: RecoveryPolicySpec
    public_metadata: Mapping[str, JsonValue]


class FeatureSpec(BaseModel):
    model_config = ConfigDict(frozen=True)
    namespace: str
    nodes: tuple[NodeSpec, ...]
    transitions: tuple[TransitionSpec, ...]


@dataclass(frozen=True)
class FeatureBindings:
    handlers: Mapping[OperationRef, OperationHandler]
    providers: Mapping[ProviderRef, ContextProvider]
    guards: Mapping[GuardRef, Guard]
```

`SurfaceSlotsSpec` models active, frame, peer, detail, form, review, status, error, and diagnostic mechanics plus lifecycle/affordance policy; it is not a single component string. Operations, providers, guards, capabilities, and surfaces are declared once as module-level typed objects and stored directly in rich nodes; product code never repeats bare string IDs. Bindings use the declared objects' typed `.ref` values. `FeatureSpec` owns nodes and internal transitions, and the compiler derives canonical operation/surface catalogs while rejecting distinct definitions that reuse an ID. Compilation consumes specs only. `bind_app` validates exactly one binding for each declared provider/guard/handler. Cross-feature transitions live only in `composition.py`. Before creating the two package directories, migrate intentional public exports and retained compatibility behavior from `app.py` and `navigation.py` into the package `__init__.py` facades, then delete the colliding module files. Corpus imports continue to resolve; the fresh Medusa application does not use the legacy runtime-subclass path.

- [ ] **Step 4: Implement segment-based route compilation without regex**

`CompiledRoutes.encode(node_id, params)` and `decode(path, session_context)` split normalized URL segments, validate declared literal/parameter positions, percent-decode values, and reject missing/extra segments. Public product handles are validated by the catalog binding. Cart, checkout, review, and confirmation routes require the same guest cookie plus a valid opaque RouteDeck resume capability bound to that session/node; missing, expired, or cross-session capabilities fail and never create replacement state.

- [ ] **Step 5: Declare all Medusa features and export the contract**

Declare the exact nodes, operations, outcomes, surfaces, routes, public/session-bound deep-link policies, and cross-feature transitions from the design. The spec plane contains no HTTP paths or callables.

Run:

```powershell
python -m pytest tests/app -q
python -m pytest tests/test_app_builder.py tests/test_navigation_policy.py tests/test_core_contract.py -q
python scripts/export_contracts.py --app-factory medusa_agent.composition:compile_medusa_app_spec --output artifacts/contracts
```

Expected: PASS and deterministic `compiled-navgraph.json`, `frontend-contract.json`, `contract-schema.json`, and `executable-test-paths.json`. Test paths cover every declared transition outcome, deep-link policy, operation safety class, review branch, and recovery branch; compilation fails when an executable path cannot be derived.

- [ ] **Step 6: Commit and push Task 3**

```powershell
Invoke-VerifiedTaskStage -TaskFiles $taskFiles
git commit -m "feat: compile feature-composed buyer graph"
git push origin saastoagent
```

### Task 4: Build Canonical Session, Navigation, Context, And Projection State

**Files:**
- Create: `routedeck_core/contracts/{projection,session,events,conversation}.py`
- Create: `routedeck_core/state/{session,reducer,history,leases}.py`
- Create: `routedeck_core/navigation/{engine,deep_links}.py`
- Create: `routedeck_core/context/{providers,scope}.py`
- Create: `routedeck_core/projection/{projector,redaction}.py`
- Create: `routedeck_core/ports/{clock,notifier,session_store}.py`
- Modify: `routedeck_testing/factories.py` with session and operation factories
- Create: `routedeck_testing/conformance.py`
- Create: `tests/conftest.py`
- Create: `tests/state/`, `tests/navigation/`, and `tests/projection/`
- Create: `examples/medusa-agent/backend/medusa_agent/session.py`
- Create: `examples/medusa-agent/backend/tests/conftest.py`
- Create: `examples/medusa-agent/backend/tests/support/medusa.py` with `buyer_market()`
- Create: `examples/medusa-agent/backend/tests/contract/test_home_session.py`

**Interfaces:**
- Consumes: `CompiledRouteDeckApp`.
- Produces: `RouteDeckSession`, `SessionSnapshot`, `PublicProjection`, `RouteDeckEvent`, `RouteDeckSessionStore`, `ProjectionProjector`, the navigation/deep-link engine, and the Medusa `buyer.home` initial-session projection.

- [ ] **Step 1: Write reducer, navigation, projection, and redaction tests**

```python
def test_projection_versions_change_only_for_public_state() -> None:
    initial = session_factory()
    private_only = reduce_session(initial, PrivateDraftStored(form_id="contact"))
    visible = reduce_session(private_only, NodeEntered(node_id="catalog.browse"))
    assert private_only.session_version == initial.session_version + 1
    assert private_only.projection_version == initial.projection_version
    assert visible.projection_version == private_only.projection_version + 1


def test_sensitive_values_never_project() -> None:
    projection = project_session(session_factory(contact_email="buyer@example.test"))
    assert "buyer@example.test" not in projection.model_dump_json()


def test_public_and_session_bound_deep_links_are_distinct() -> None:
    assert open_deep_link("/products/t-shirt", session=None).node_id == "catalog.product"
    with pytest.raises(SessionRequired):
        open_deep_link("/cart", session=None)
    with pytest.raises(SessionRequired):
        open_deep_link("/checkout/review", session=None)
    with pytest.raises(CapabilityMismatch):
        open_deep_link(
            "/orders/confirmation/confirmation",
            session=session_factory(),
            resume_capability=capability_for_other_session(),
        )


def test_medusa_home_session_uses_compiled_buyer_graph() -> None:
    session = create_medusa_session(session_id="session-1", market=buyer_market())
    assert session.current.node_id == "buyer.home"
    assert project_session(session).surfaces["active"].component == "buyer.welcome"
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python -m pytest tests/state tests/navigation tests/projection -q`

Expected: FAIL because canonical session contracts and reducers do not exist.

- [ ] **Step 3: Implement immutable state and reducer events**

```python
class RouteDeckSession(BaseModel):
    model_config = ConfigDict(frozen=True)
    session_id: str
    schema_version: int
    navgraph_version: str
    session_version: int
    projection_version: int
    event_cursor: int
    current: Location
    back_stack: tuple[Location, ...] = ()
    forward_stack: tuple[Location, ...] = ()
    conversation: tuple[ConversationTurn, ...] = ()
    private_state: PrivateSessionState
    operation: OperationState | None = None


class RouteDeckSessionStore(Protocol):
    async def create(self, initial: RouteDeckSession) -> SessionSnapshot: ...
    async def load(self, session_id: str) -> SessionSnapshot: ...
    async def find_attempt(self, session_id: str, request_id: str) -> OperationAttempt | None: ...
    async def acquire_turn(self, claim: TurnClaim) -> TurnLease: ...
    async def stage_review(self, lease: TurnLease, review: PendingReview) -> SessionSnapshot: ...
    async def claim_execution(self, lease: TurnLease, attempt: OperationAttempt) -> ExecutionClaim: ...
    async def record_execution_result(
        self, claim: ExecutionClaim, result: JournaledExecutionResult,
    ) -> None: ...
    async def commit_state(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
    ) -> SessionSnapshot: ...
    async def finalize_turn(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        turns: Sequence[FinalizedConversationTurn],
        events: Sequence[RouteDeckEvent],
    ) -> SessionSnapshot: ...
    async def interrupt_turn(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        failure: RouteDeckFailure,
        events: Sequence[RouteDeckEvent],
    ) -> SessionSnapshot: ...
    async def commit_attempt(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
        terminal: AttemptTerminalState,
    ) -> SessionSnapshot: ...
    async def mark_external_outcome_unknown(
        self, claim: ExecutionClaim, failure: RouteDeckFailure,
    ) -> SessionSnapshot: ...
    async def release_turn(self, lease: TurnLease) -> None: ...
    async def events_after(self, session_id: str, cursor: int, limit: int) -> EventPage: ...
    async def load_private_blob(self, session_id: str, form_id: str) -> bytes | None: ...
    async def save_private_blob(
        self,
        lease: TurnLease,
        expected_session_version: int,
        form_id: str,
        encrypted_value: bytes,
        next_state: RouteDeckSession,
    ) -> SessionSnapshot: ...
```

`TurnClaim` carries session ID, expected session version, request ID/fingerprint, owner kind, and optional parent turn ID. `TurnLease`, `ExecutionClaim`, and every write token are opaque fenced capabilities issued by the store. This port makes attempt identity, review staging, pre-send claims, typed result journaling, state/outbox commit, unknown-outcome commit, replay, and private blobs explicit; adapters may not simulate them around a simple CAS. Reducer functions remain pure and have no clocks, I/O, product handlers, or fallback defaults. Inject `Clock` for timestamps at the orchestration boundary.

- [ ] **Step 4: Implement context scoping and strict public projection**

Projection contains the current node, legal operations, compiled navigation, allowlisted entity handles, surfaces, status, safe failures, and read-only diagnostics. Context scope exposes only data declared for the current node and operation. Private Medusa IDs and form values stay in private state. `medusa_agent/session.py` consumes these APIs to construct and project the real buyer graph's home session; no parallel product state model is introduced.

- [ ] **Step 5: Run core state tests and compatibility regression**

Run:

```powershell
python -m pytest tests/state tests/navigation tests/projection examples/medusa-agent/backend/tests/contract/test_home_session.py -q
python -m pytest tests/test_core_contract.py tests/test_navigation_policy.py tests/test_surface_registry.py -q
```

Expected: new tests PASS; retained compatibility tests PASS through facades or are replaced in the same commit with equivalent assertions.

- [ ] **Step 6: Commit and push Task 4**

```powershell
Invoke-VerifiedTaskStage -TaskFiles $taskFiles
git commit -m "feat: add canonical RouteDeck session state"
git push origin saastoagent
```

### Task 5: Implement One Supervised Operation Runner And Review Lifecycle

**Files:**
- Modify: `routedeck_core/contracts/failures.py`
- Complete: `routedeck_core/contracts/operations.py` with execution contracts
- Create: `routedeck_core/ports/executor.py`
- Create: `routedeck_core/supervision/{runner,guards,reviews,outcomes}.py`
- Create: `tests/supervision/{test_operation_runner,test_idempotency,test_guards,test_review_lifecycle,test_external_outcome_unknown,test_crash_windows}.py`
- Rewrite: `routedeck_core/dispatch.py` as a no-fallback compatibility facade
- Rewrite: `tests/test_action_dispatcher.py` to reject default handlers
- Create: `examples/medusa-agent/backend/medusa_agent/medusa/client/{protocol,models}.py`
- Create: `examples/medusa-agent/backend/medusa_agent/medusa/__init__.py` and `medusa/client/__init__.py`
- Create: `examples/medusa-agent/backend/medusa_agent/features/cart/handlers.py`
- Modify: `examples/medusa-agent/backend/tests/conftest.py`
- Complete: `examples/medusa-agent/backend/tests/support/medusa.py`
- Create: `examples/medusa-agent/backend/tests/support/runtime.py`
- Create: `examples/medusa-agent/backend/tests/contract/test_runner_binding.py`

**Interfaces:**
- Consumes: canonical sessions, compiled operations/bindings, `RouteDeckSessionStore`, and `OperationExecutor`.
- Produces: `RouteDeckOperationRunner.run`, `RouteDeckOperationRunner.accept_review`, typed supervision decisions, operation attempts, durable lifecycle events, and a Medusa `cart.create` binding that can execute only through the runner.

- [ ] **Step 1: Write failing supervision and shared-path tests**

```python
@pytest.mark.asyncio
async def test_blocked_operation_never_invokes_executor(runner_factory) -> None:
    executor = RecordingExecutor()
    runner = runner_factory(executor=executor)
    result = await runner.run(
        operation_request(operation_id="cart.add_item", entity_key="forged")
    )
    assert result.disposition == "blocked"
    assert executor.calls == []


@pytest.mark.asyncio
async def test_ui_and_agent_sources_use_the_same_runner(runner) -> None:
    ui = await runner.run(operation_request(source="surface", request_id="ui-1"))
    agent = await runner.run(operation_request(source="agent", request_id="agent-1"))
    assert ui.evidence.phases == agent.evidence.phases


@pytest.mark.asyncio
async def test_agent_child_attempts_share_one_serial_turn_lease(runner, store) -> None:
    turn = await runner.begin_turn(chat_turn_claim(request_id="turn-1"))
    await runner.run(operation_request(source="agent", request_id="tool-1"), turn=turn)
    await runner.run(operation_request(source="agent", request_id="tool-2"), turn=turn)
    assert await store.turn_claim_count("turn-1") == 1
    assert await store.child_attempt_ids("turn-1") == ("tool-1", "tool-2")


@pytest.mark.asyncio
async def test_model_only_turn_finalizes_and_releases_lease(runner, store) -> None:
    turn = await runner.begin_turn(chat_turn_claim(request_id="turn-text"))
    snapshot = await runner.complete_turn(
        turn,
        expected_session_version=1,
        turns=finalized_turns(user="hello", assistant="welcome"),
    )
    assert snapshot.state.conversation[-1].status == "finalized"
    assert await store.active_turn("turn-text") is None


@pytest.mark.asyncio
async def test_interrupted_turn_persists_no_partial_assistant(runner, store) -> None:
    turn = await runner.begin_turn(chat_turn_claim(request_id="turn-crash"))
    snapshot = await runner.interrupt_turn(
        turn,
        expected_session_version=1,
        failure=turn_interrupted_failure(),
    )
    assert snapshot.state.conversation[-1].status == "turn_interrupted"
    assert "partial" not in snapshot.model_dump_json()
    assert await store.active_turn("turn-crash") is None


@pytest.mark.asyncio
async def test_review_acceptance_executes_frozen_arguments_once(runner) -> None:
    proposed = await runner.run(place_order_request(request_id="propose-1"))
    assert proposed.disposition == "requires_review"
    completed = await runner.accept_review(
        proposed.review.id,
        request_id="approve-1",
        expected_session_version=proposed.session_version,
    )
    replay = await runner.accept_review(
        proposed.review.id,
        request_id="approve-2",
        expected_session_version=completed.session_version,
    )
    assert completed.disposition == "completed"
    assert replay.failure.code == "review_already_resolved"
    assert runner.executor.call_count("checkout.place_order") == 1


@pytest.mark.asyncio
async def test_medusa_cart_create_binding_cannot_bypass_runner(
    medusa_runtime, client: RecordingMedusaStoreClient,
) -> None:
    result = await medusa_runtime.runner.run(
        operation_request(operation_id="cart.create", source="system", request_id="cart-create-1")
    )
    assert result.disposition == "completed"
    assert client.calls == ["create_cart"]
    assert result.evidence.source == "system"
```

- [ ] **Step 2: Run supervision tests and verify RED**

Run: `python -m pytest tests/supervision tests/test_action_dispatcher.py -q`

Expected: FAIL because the runner and durable review contracts do not exist.

- [ ] **Step 3: Implement the executor and runner contracts**

```python
class DeliveryPhase(StrEnum):
    NOT_SENT = "not_sent"
    POSSIBLY_SENT = "possibly_sent"
    RESPONSE_RECEIVED = "response_received"


class OperationExecutor(Protocol):
    async def execute(
        self, binding: OperationBinding, arguments: Mapping[str, Any], context: ExecutionContext,
    ) -> OperationOutcome: ...


class RouteDeckOperationRunner:
    async def begin_turn(self, claim: TurnClaim) -> TurnLease: ...
    async def run(
        self, request: OperationRequest, *, turn: TurnLease | None = None,
    ) -> OperationResult: ...
    async def complete_turn(
        self,
        turn: TurnLease,
        expected_session_version: int,
        turns: Sequence[FinalizedConversationTurn],
    ) -> SessionSnapshot: ...
    async def interrupt_turn(
        self,
        turn: TurnLease,
        expected_session_version: int,
        failure: RouteDeckFailure,
    ) -> SessionSnapshot: ...
    async def accept_review(
        self, review_id: str, request_id: str, expected_session_version: int,
    ) -> OperationResult: ...
    async def reject_review(
        self, review_id: str, request_id: str, expected_session_version: int,
    ) -> OperationResult: ...
```

The runner performs, in order: idempotency lookup, turn-lease acquisition or validation, version/input/entity validation, context refresh, guards, review staging or execution claim, injected executor call, result journaling, typed outcome validation, state/projection/outbox commit, and lease release. A direct UI dispatch supplies no turn and receives one short lease. A chat request acquires one parent turn lease; each serial structured tool call is a child attempt under that same lease and never acquires a competing lease. Parallel child writes are rejected. `complete_turn` atomically persists finalized conversation content/state/events and releases the parent lease; `interrupt_turn` atomically records `turn_interrupted` and releases it without treating partial assistant text as final. Review staging commits and releases the parent turn before waiting; accept/reject are new versioned mutations. No default handler or exception-text classification is permitted. Define the Medusa client protocol/models needed by `cart.create` and bind its ordinary typed handler through `composition.py`; the HTTP implementation remains Task 11.

- [ ] **Step 4: Implement frozen reviews and state-change invalidation**

Review records contain normalized arguments, proposal fingerprint, operation-spec version, projection version, refreshed totals fingerprint, expiry, and resolution. Acceptance loads the recorded arguments, refreshes declared authoritative context, re-runs guards, and creates a new execution lease. Changed cart facts return `review_stale` and never call the executor.

- [ ] **Step 5: Implement explicit uncertain-write semantics**

If an executor reports `possibly_sent`, or a write response cannot be durably journaled, commit `external_outcome_unknown`, remove the write from legal operations, and project only the declared recovery action. If a typed result was journaled before a crash, recovery applies it without invoking the executor again.

- [ ] **Step 6: Run focused and legacy boundary tests**

Run:

```powershell
python -m pytest tests/supervision tests/test_action_dispatcher.py examples/medusa-agent/backend/tests/contract/test_runner_binding.py -q
python -m pytest tests/test_operation_policy.py tests/test_runtime_ownership.py -q
```

Expected: PASS; runtime ownership tests assert the host executor owns product invocation and the Medusa app does not subclass `RouteDeckRuntimeBase`.

- [ ] **Step 7: Commit and push Task 5**

```powershell
Invoke-VerifiedTaskStage -TaskFiles $taskFiles
git commit -m "feat: supervise operations through one runner"
git push origin saastoagent
```

### Task 6: Add Durable Fenced SQLite State And Encrypted Private Data

**Files:**
- Create: `routedeck_core/contracts/retention.py`
- Create: `routedeck_sqlite/{connection,schema,migrations,codec,instance_lease,store}.py`
- Create: `tests/sqlite/{test_schema_migrations,test_session_store,test_cas_and_claims,test_instance_lease,test_outbox_replay,test_restart_cleanup,test_encrypted_blobs}.py`
- Create: `tests/conformance/test_store_conformance.py`
- Modify: `routedeck_testing/conformance.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/composition.py`
- Create: `examples/medusa-agent/backend/tests/contract/test_persistent_session.py`

**Interfaces:**
- Consumes: `RouteDeckSessionStore`, runner claims/results, events, and the injected clock.
- Produces: `RouteDeckRetentionPolicy`, `SqliteSessionStore`, `FernetSensitiveCodec`, durable request/result replay, outbox replay, cleanup, fenced single-instance enforcement, and a Medusa composition that reopens the same buyer session after process reconstruction.

- [ ] **Step 1: Write failing persistence and crash-window tests**

```python
@pytest.mark.asyncio
async def test_cas_rejects_stale_session_version(store: SqliteSessionStore) -> None:
    saved = await store.create(session_factory())
    lease = await store.acquire_turn(
        chat_turn_claim(request_id="mutation-1", expected_session_version=saved.session_version)
    )
    await store.commit_state(lease, saved.session_version, next_session(saved), [])
    with pytest.raises(SessionVersionConflict):
        await store.acquire_turn(
            chat_turn_claim(request_id="mutation-2", expected_session_version=saved.session_version)
        )


@pytest.mark.asyncio
async def test_second_live_process_is_fenced(database_path: Path) -> None:
    first = await SqliteSessionStore.open(database_path, instance_id="first")
    with pytest.raises(RouteDeckInstanceAlreadyRunning):
        await SqliteSessionStore.open(database_path, instance_id="second")
    await first.close()


@pytest.mark.asyncio
async def test_sensitive_blob_is_not_plaintext(
    store: SqliteSessionStore, codec: SensitiveCodec,
) -> None:
    saved = await store.create(session_factory())
    lease = await store.acquire_turn(
        chat_turn_claim(request_id="private-1", expected_session_version=saved.session_version)
    )
    next_state = reduce_session(saved.state, PrivateDraftStored(form_id="contact"))
    encrypted = codec.encrypt(b'{"email":"buyer@example.test"}')
    await store.save_private_blob(
        lease, saved.session_version, "contact", encrypted, next_state,
    )
    assert b"buyer@example.test" not in store.database_path.read_bytes()


@pytest.mark.asyncio
async def test_conversation_content_is_not_plaintext(store: SqliteSessionStore) -> None:
    await persist_finalized_turn(store, user_text="private hello", assistant_text="private reply")
    database = store.database_path.read_bytes()
    assert b"private hello" not in database
    assert b"private reply" not in database


@pytest.mark.asyncio
async def test_raw_exception_text_is_neither_persisted_nor_projected(
    runner_factory, store: SqliteSessionStore,
) -> None:
    result = await runner_factory(store=store, executor=SecretRaisingExecutor()).run(
        operation_request(request_id="secret-failure-1")
    )
    assert result.failure.code == "unexpected_executor_failure"
    assert "secret-token-in-exception" not in result.projection.model_dump_json()
    assert b"secret-token-in-exception" not in store.database_path.read_bytes()


@pytest.mark.asyncio
async def test_medusa_composition_reopens_home_session(database_path: Path) -> None:
    first_runtime = build_medusa_runtime(database_path)
    first = await first_runtime.create_session()
    await first_runtime.close()
    second_runtime = build_medusa_runtime(database_path)
    reopened = await second_runtime.load_session(first.session_id)
    assert reopened.current.node_id == "buyer.home"
    await second_runtime.close()
```

- [ ] **Step 2: Run SQLite tests and verify RED**

Run: `python -m pytest tests/sqlite tests/conformance/test_store_conformance.py -q`

Expected: FAIL because `SqliteSessionStore` does not exist.

- [ ] **Step 3: Implement the versioned schema and migration runner**

Schema v1 contains explicit tables for `schema_migrations`, `application_lease`, `sessions`, `operation_attempts`, `execution_results`, `events`, `private_blobs`, and encrypted `conversation_blobs`. Representative constraints:

```sql
CREATE TABLE sessions (
  session_id TEXT PRIMARY KEY,
  schema_version INTEGER NOT NULL,
  navgraph_version TEXT NOT NULL,
  session_version INTEGER NOT NULL,
  projection_version INTEGER NOT NULL,
  event_cursor INTEGER NOT NULL,
  state_json TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX operation_request_identity
ON operation_attempts(session_id, request_id);
```

All migrations run inside `BEGIN IMMEDIATE`; no migration failure is swallowed.

- [ ] **Step 4: Implement connection and fenced instance ownership**

Use stdlib `sqlite3` through `asyncio.to_thread`. On every connection set WAL, foreign keys, synchronous `FULL`, and a typed `busy_timeout` whose standalone default is exactly five seconds. Every write path, not only migrations, uses a short `BEGIN IMMEDIATE` transaction. `application_lease` stores instance ID, fencing token, heartbeat, and expiry. Every session write and execution claim includes the current fencing token in its predicate. Startup configuration rejects worker counts other than one before serving; a second live process is independently rejected by the database lease.

- [ ] **Step 5: Implement required encryption without plaintext fallback**

```python
class SensitiveCodec(Protocol):
    def encrypt(self, value: bytes) -> bytes: ...
    def decrypt(self, value: bytes) -> bytes: ...


class FernetSensitiveCodec:
    def __init__(self, key: str) -> None:
        if not key:
            raise MissingEncryptionKey("ROUTEDECK_STATE_ENCRYPTION_KEY is required")
        self._fernet = Fernet(key.encode("ascii"))
```

Private blobs and conversation content are encrypted before persistence. The session serializer extracts finalized user/assistant content into `conversation_blobs`; plaintext `state_json` retains only turn IDs, roles/status, ordering metadata, and encrypted-blob references, then load rehydrates content through the required codec. Public projections/events never reuse the encrypted payload field. Bind `SqliteSessionStore` in Medusa `composition.py`; the application may not instantiate an in-memory product store.

- [ ] **Step 6: Implement outbox replay, result recovery, and bounded cleanup**

`events_after(session_id, cursor, limit)` returns ordered durable frames. Missing retained cursors return an explicit reset requirement. `RouteDeckRetentionPolicy.standalone_default()` contains the approved values: unfinished idle TTL 24 hours, unfinished absolute TTL seven days, completed TTL 24 hours after confirmation, event retention 24 hours or 1,000 events per session, operation journal until session deletion, cleanup at startup and every 15 minutes, and an explicit bounded cleanup batch size. Cleanup deletes expired RouteDeck sessions/blobs/conversation/events/attempts in bounded batches and never calls Medusa or deletes commerce records. A stored schema/navgraph version without a declared migration fails as `session_upgrade_required`; it never resets state.

- [ ] **Step 7: Run persistence, crash, and conformance suites**

Run:

```powershell
python -m pytest tests/sqlite tests/conformance/test_store_conformance.py tests/supervision/test_crash_windows.py examples/medusa-agent/backend/tests/contract/test_persistent_session.py -q
```

Expected: PASS, including reopen/recovery with zero extra executor calls.

- [ ] **Step 8: Commit and push Task 6**

```powershell
Invoke-VerifiedTaskStage -TaskFiles $taskFiles
git commit -m "feat: persist RouteDeck sessions in SQLite"
git push origin saastoagent
```

### Task 7: Expose Generic FastAPI Session, Dispatch, Private-Form, And SSE Transport

**Files:**
- Create: `routedeck_fastapi/{dependencies,router,sse}.py`
- Create: `tests/fastapi/{test_session_transport,test_dispatch_review_transport,test_private_form_transport,test_sse_transport}.py`
- Create: `tests/events/{test_event_contracts,test_sse_encoding,test_replay_and_gaps}.py`
- Create: `tests/events/support.py`
- Create: `examples/medusa-agent/backend/main.py`
- Create: `examples/medusa-agent/backend/medusa_agent/api/__init__.py`
- Create: `examples/medusa-agent/backend/medusa_agent/api/health.py`
- Create: `examples/medusa-agent/backend/tests/contract/test_routedeck_mount.py`

**Interfaces:**
- Consumes: compiled app, `RouteDeckOperationRunner`, `RouteDeckSessionStore`, notifier, projector, and private-form codec.
- Produces: `create_routedeck_router(...)`, stable generic `/api/routedeck/*` endpoints, and the Medusa FastAPI app mounting those routes without reimplementing them.

- [ ] **Step 1: Write failing HTTP and SSE contract tests**

```python
def test_session_bootstrap_sets_private_cookie(client: TestClient) -> None:
    response = client.post("/api/routedeck/sessions")
    assert response.status_code == 201
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]
    assert response.json()["projection"]["graph_node"] == "buyer.home"


def test_private_form_is_no_store_and_absent_from_projection(client: TestClient) -> None:
    response = client.put(
        "/api/routedeck/private-forms/contact",
        json={
            "request_id": "private-form-1",
            "expected_session_version": 1,
            "value": {"email": "buyer@example.test"},
        },
    )
    assert response.headers["cache-control"] == "no-store"
    projection = client.get("/api/routedeck/session").text
    assert "buyer@example.test" not in projection


def test_sse_replays_after_cursor(client: TestClient) -> None:
    with client.stream("GET", "/api/routedeck/events?after=2") as response:
        frames = take_sse_frames(response, count=2)
    assert [frame.id for frame in frames] == [3, 4]


def test_medusa_app_mounts_generic_transport_once(client: TestClient) -> None:
    assert client.post("/api/routedeck/sessions").status_code == 201
    assert client.get("/api/medusa-agent/health").json() == {"status": "ok"}
```

- [ ] **Step 2: Run transport tests and verify RED**

Run: `python -m pytest tests/fastapi tests/events -q`

Expected: FAIL because the generic router and SSE encoder do not exist.

- [ ] **Step 3: Implement explicit endpoints**

Mount exactly:

```text
POST /api/routedeck/sessions
GET  /api/routedeck/session
POST /api/routedeck/dispatch
POST /api/routedeck/reviews/{review_id}/accept
POST /api/routedeck/reviews/{review_id}/reject
GET  /api/routedeck/events?after=<cursor>
GET  /api/routedeck/private-forms/{form_id}
PUT  /api/routedeck/private-forms/{form_id}
GET  /api/routedeck/inspect
```

The router contains no product endpoints. Every dispatch, navigation, private-form save, and review accept/reject request carries a globally unique request ID and expected session version; review arguments are never accepted from the client. Session creation uses a cryptographically random opaque token in an `HttpOnly`, `SameSite=Lax` cookie; session IDs never enter URLs or browser storage. Missing, expired, and cross-session capability bindings fail explicitly and never create replacement state. The router accepts injected dependencies and maps stable failures to explicit HTTP statuses: 400 contract, 404 unknown session/route, 409 version/request/lease conflict, 410 expired session, 422 needs-input, 503 dependency unavailable, and 500 internal invariant. Medusa `main.py` mounts it once and adds only product-owned health/chat APIs.

- [ ] **Step 4: Implement durable SSE replay and reset semantics**

SSE frames include `id`, event type, session version, optional projection version, and public payload. Read `Last-Event-ID` or `after`; reject conflicting values. Replay persisted events before subscribing to notifier wakeups. Emit `stream_reset_required` and close when the cursor predates retention. Heartbeats are comments without cursors.

- [ ] **Step 5: Run transport and core regression suites**

Run:

```powershell
python -m pytest tests/fastapi tests/events examples/medusa-agent/backend/tests/contract/test_routedeck_mount.py -q
python -m pytest tests/state tests/supervision tests/sqlite -q
```

Expected: PASS; SSE reconnect never replays a product operation.

- [ ] **Step 6: Commit and push Task 7**

```powershell
Invoke-VerifiedTaskStage -TaskFiles $taskFiles
git commit -m "feat: expose RouteDeck FastAPI transport"
git push origin saastoagent
```

### Task 8: Replace Topology Mirroring With LangGraph Middleware And Tool Wrappers

**Files:**
- Create: `routedeck_langgraph/{middleware,tool_wrapper,model_context}.py`
- Rewrite: `routedeck_langgraph/__init__.py`
- Convert: `routedeck_langgraph/graph.py` to a compatibility-only deprecation facade
- Create: `tests/langgraph/{test_model_context,test_middleware_tool_filtering,test_tool_wrapper,test_review_short_circuit,test_history_reconstruction}.py`
- Create: `tests/langgraph/support.py`
- Rewrite: `tests/test_langgraph_adapter.py`
- Create: `routedeck_testing/scripted_model.py`
- Create: `examples/medusa-agent/backend/medusa_agent/agent.py`
- Create: `examples/medusa-agent/backend/tests/contract/test_agent_middleware.py`

**Interfaces:**
- Consumes: `RouteDeckOperationRunner`, `RouteDeckSessionStore`, scoped context projector, and bound LangGraph tool handlers.
- Produces: `RouteDeckMiddleware`, `RouteDeckToolWrapper`, `build_model_context`, raw `ToolNode` wrapper support without topology mutation, and an injected-model Medusa agent factory proving the consumer path.

- [ ] **Step 1: Write failing middleware and raw-graph tests**

```python
@pytest.mark.asyncio
async def test_middleware_exposes_only_current_legal_tools(runtime) -> None:
    request = model_request(session_at("checkout.review"), tools=all_product_tools())
    transformed = await RouteDeckMiddleware(runtime).before_model(request)
    assert [tool.name for tool in transformed.tools] == ["checkout.place_order"]


@pytest.mark.asyncio
async def test_review_short_circuits_tool_handler() -> None:
    handler = AsyncMock()
    result = await wrapper(handler).wrap(place_order_tool_call())
    assert result.status == "requires_review"
    handler.assert_not_awaited()


def test_raw_state_graph_topology_is_unchanged(runtime) -> None:
    graph = make_raw_graph()
    before = graph_edges(graph)
    attach_route_deck_wrappers(graph, runtime)
    assert graph_edges(graph) == before


@pytest.mark.asyncio
async def test_medusa_agent_factory_uses_routedeck_middleware(runtime) -> None:
    agent = create_medusa_agent(model=ScriptedToolModel([]), runtime=runtime)
    assert agent.middleware_types == (RouteDeckMiddleware,)
```

- [ ] **Step 2: Run LangGraph tests and verify RED**

Run: `python -m pytest tests/langgraph tests/test_langgraph_adapter.py -q`

Expected: FAIL because current adapter builds one execution node per RouteDeck nav node.

- [ ] **Step 3: Implement scoped model context and tool filtering**

`build_model_context` receives a session snapshot and emits current node, active surface, safe visible entities, legal tool schemas, needs-input/review status, and recent allowlisted observations. It never emits private forms, raw Medusa IDs not in the operation allowlist, diagnostics, or unrelated history.

- [ ] **Step 4: Implement standard middleware and raw ToolNode wrapping**

For standard `create_agent`, middleware derives context before each model call and wraps each structured tool call through the shared runner. For raw graphs, export an `awrap_tool_call(request, handler)` compatible callback. The handler is the injected executor callback; wrapper results are typed tool messages, not guessed assistant prose. Add `create_medusa_agent(model, runtime)` with an injected scripted model so this task proves the real Medusa composition without requiring live credentials; Task 16 completes prompt/live-model/chat behavior.

- [ ] **Step 5: Retire topology generation from the golden path**

`build_route_deck_state_graph` raises a targeted deprecation error directing users to middleware/wrappers. Do not silently call a new path. Compatibility remains importable only until Corpus has a separately approved migration.

- [ ] **Step 6: Run LangGraph and supervision regression**

Run:

```powershell
python -m pytest tests/langgraph tests/test_langgraph_adapter.py tests/supervision examples/medusa-agent/backend/tests/contract/test_agent_middleware.py -q
```

Expected: PASS; allowed handlers run once, blocked/reviewed handlers run zero times, and raw graph topology is unchanged.

- [ ] **Step 7: Commit and push Task 8**

```powershell
Invoke-VerifiedTaskStage -TaskFiles $taskFiles
git commit -m "feat: integrate RouteDeck through LangGraph middleware"
git push origin saastoagent
```

### Task 9: Split The Frontend Into Headless Core, React, And Testing Workspaces

**Files:**
- Create: `package.json`
- Create: `pnpm-workspace.yaml`
- Create: `tsconfig.base.json`
- Create: `vitest.workspace.ts`
- Create: `packages/core/{package.json,tsconfig.json,src/index.ts}`
- Create: `packages/core/src/contracts/{generated,decode}.ts`
- Create: `packages/core/src/client/{client,http,sse,errors}.ts`
- Create: `packages/core/src/store/{state,reducer,store,selectors}.ts`
- Create: `packages/core/src/routing/{codec,history,controller}.ts`
- Create: `packages/core/src/private-forms/{client,state}.ts`
- Create: `packages/core/tests/{contracts,event-reducer,store,sse,routing,private-forms}.test.ts`
- Create: `packages/testing/{package.json,tsconfig.json}`
- Create: `packages/testing/src/{index,factories,storeHarness,sseHarness}.ts`
- Create: `packages/testing/tests/harnesses.test.ts`
- Modify: `scripts/export_contracts.py`
- Create: `examples/medusa-agent/frontend/src/app/createRouteDeck.ts`
- Create: `examples/medusa-agent/frontend/src/routedeck/client.ts`
- Replace: `examples/medusa-agent/frontend/package.json`
- Create: `examples/medusa-agent/frontend/tsconfig.json`
- Modify: `examples/medusa-agent/frontend/vite.config.ts`

**Interfaces:**
- Consumes: generated generic schema, compiled Medusa frontend contract, FastAPI transport, and SSE protocol.
- Produces: `createRouteDeckStore`, `RouteDeckClient`, strict event reducer, route/history controller, private-form client, selectors, and reusable test harnesses.

- [ ] **Step 1: Create the pnpm workspace and failing independence tests**

Root metadata:

```json
{
  "name": "routedeck-workspace",
  "private": true,
  "packageManager": "pnpm@11.7.0",
  "engines": { "node": ">=22.12.0" },
  "scripts": {
    "test": "pnpm -r test",
    "typecheck": "pnpm -r typecheck",
    "build": "pnpm -r build"
  }
}
```

Workspace membership is explicit:

```yaml
packages:
  - "packages/*"
  - "examples/medusa-agent/frontend"
```

The example package name is `@routedeck/medusa-agent`. In Task 9 it depends on the workspace `@routedeck/core` package while retaining its existing React shell; Task 10 adds the workspace `@routedeck/react` dependency when that package is created.

```ts
it("keeps @routedeck/core independent of React", async () => {
  const pkg = await readPackageJson("packages/core/package.json")
  expect({ ...pkg.dependencies, ...pkg.peerDependencies }).not.toHaveProperty("react")
})
```

- [ ] **Step 2: Install with bundled Node/pnpm and verify RED**

Run:

```powershell
$env:PATH="C:\Users\ragha\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin;C:\Users\ragha\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\fallback;$env:PATH"
pnpm install
pnpm --filter @routedeck/core test
```

Expected: FAIL because headless store modules do not exist.

- [ ] **Step 3: Generate generic TypeScript contracts from Python schema**

`scripts/export_contracts.py` writes a deterministic JSON Schema. The workspace build runs `json-schema-to-typescript` to produce `packages/core/src/contracts/generated.ts`; this file is generated and checked for drift, never hand-edited. The product navgraph remains fetched runtime data rather than a TypeScript catalog.

- [ ] **Step 4: Implement strict client and reducer contracts**

```ts
export interface RouteDeckStore {
  getState(): RouteDeckClientState
  subscribe(listener: () => void): () => void
  bootstrap(): Promise<void>
  dispatch(request: RouteDeckDispatchRequest): Promise<RouteDeckDispatchResult>
  receiveEvent(event: RouteDeckEvent): void
  resync(): Promise<void>
  dispose(): void
}

export function reduceEvent(state: RouteDeckClientState, event: RouteDeckEvent): RouteDeckClientState {
  if (event.cursor <= state.eventCursor) return state
  if (event.cursor !== state.eventCursor + 1) return { ...state, syncStatus: "resync_required" }
  return applyTypedEvent(state, event)
}
```

Strict decoders throw `RouteDeckContractError`; they never synthesize empty projections, default operations, or fallback surfaces.

- [ ] **Step 5: Implement cursor-aware SSE and route/history control**

Bootstrap snapshot first, then connect after its cursor. Ignore duplicates, resync on gaps, obey `stream_reset_required`, and dispose listeners cleanly. Route matching is compiled segment matching without regex/path-prefix heuristics. Public catalog links can create a session; session-bound cart, checkout, review, and confirmation links require the current cookie-backed session and matching resume capability.

- [ ] **Step 6: Implement private-form memory state and test-only harnesses**

Private-form values are loaded/saved through the no-store API and held only in an in-memory form store. `@routedeck/testing` exports snapshot/event factories, an SSE harness, and store assertions; it is never imported by runtime product code.

- [ ] **Step 7: Consume the package in the Medusa frontend bootstrap**

```ts
export const routeDeck = createRouteDeckStore({
  client: createRouteDeckClient({ baseUrl: "/api/routedeck" }),
  history: createBrowserHistoryAdapter(window),
})
```

Delete the example's direct projection/event hooks only after the new bootstrap test passes.

- [ ] **Step 8: Run package and consumer tests**

Run:

```powershell
pnpm --filter @routedeck/core test
pnpm --filter @routedeck/testing test
pnpm typecheck
pnpm build
```

Expected: PASS with zero React dependency in core and zero contract drift.

- [ ] **Step 9: Commit and push Task 9**

```powershell
Invoke-VerifiedTaskStage -TaskFiles $taskFiles
git commit -m "feat: add headless RouteDeck frontend store"
git push origin saastoagent
```

### Task 10: Build React Bindings, Surface Primitives, And Inspector

**Files:**
- Create: `packages/react/{package.json,tsconfig.json,src/index.ts}`
- Create: `packages/react/src/provider/RouteDeckProvider.tsx`
- Create: `packages/react/src/hooks/{store,projection,navigation,operations,status}.ts`
- Create: `packages/react/src/surfaces/{registry,RouteDeckSurfaceHost}.tsx`
- Create: `packages/react/src/navigation/{RouteDeckLink,RouteDeckNavigationControls,RouteDeckHistorySync}.tsx`
- Create: `packages/react/src/private-forms/{useRouteDeckPrivateForm,RouteDeckPrivateForm}.tsx`
- Create: `packages/react/src/review/{RouteDeckReview,RouteDeckNeedsInput}.tsx`
- Create: `packages/react/src/status/{RouteDeckStatus,RouteDeckError}.tsx`
- Create: `packages/react/src/inspector/{NavGraphInspector,topology,edgeRouting}.tsx`
- Create: `packages/react/tests/`
- Create: `packages/testing/src/componentHarness.tsx`
- Modify: `examples/medusa-agent/frontend/package.json` to add `@routedeck/react`
- Create: `examples/medusa-agent/frontend/src/routedeck/surfaces.tsx`
- Create: `examples/medusa-agent/frontend/src/app/BuyerWelcomeSurface.tsx`
- Create: `examples/medusa-agent/frontend/src/tests/app-shell.test.tsx`
- Remove after migration: `react/`

**Interfaces:**
- Consumes: `@routedeck/core` store and compiled surface component keys.
- Produces: provider/hooks, typed product surface registry, navigation, private-form, needs-input/review/status/error primitives, and read-only navgraph inspector.

- [ ] **Step 1: Write failing provider, surface, review, and inspector tests**

```tsx
it("renders the registered product surface", () => {
  const registry = defineRouteDeckSurfaceRegistry({ "buyer.welcome": BuyerWelcomeSurface })
  render(<RouteDeckProvider store={storeAt("buyer.home")}><RouteDeckSurfaceHost registry={registry} /></RouteDeckProvider>)
  expect(screen.getByRole("heading", { name: /shop with medusa/i })).toBeVisible()
})

it("fails visibly for an unknown component key", () => {
  renderHost({ component: "unknown.surface" })
  expect(screen.getByText(/surface component is not registered/i)).toBeVisible()
})

it("keeps inspector node selection read-only", async () => {
  await user.click(screen.getByText("checkout.review"))
  expect(store.dispatch).not.toHaveBeenCalled()
  expect(window.location.pathname).toBe("/")
})
```

- [ ] **Step 2: Run React tests and verify RED**

Run: `pnpm --filter @routedeck/react test`

Expected: FAIL because React package primitives do not exist.

- [ ] **Step 3: Implement provider/hooks with `useSyncExternalStore`**

Provider requires a store; it does not create a static fallback store. Hooks are thin selectors over the headless package and do not duplicate reducer or routing logic.

- [ ] **Step 4: Implement the surface registry and host**

```ts
export function defineRouteDeckSurfaceRegistry<T extends SurfaceRegistry>(registry: T): T {
  return Object.freeze({ ...registry })
}
```

The host resolves active, frame, peer, detail, form, review, status, error, and diagnostic slots from projection, applies compiled lifecycle/affordance rules, renders product components by compiled key, and uses `RouteDeckError` for missing registrations. No product-specific slot precedence or component key is hardcoded in the framework host.

- [ ] **Step 5: Implement navigation, private-form, review, and status primitives**

All mutation controls dispatch declared operations through the store. Private form hooks never copy values into projection. Review accept/reject dispatch only the review ID, globally unique request ID, and current expected session version; arguments remain server-frozen.

- [ ] **Step 6: Migrate topology/edge-routing algorithms into the inspector**

Reuse deterministic algorithms from `react/src/routeDeckDebuggerTopology.ts` and `routeDeckDebuggerRouting.ts`, adapting them to compiled navgraph contracts. Remove product-specific positions and hardcoded edges. Inspector selection changes only diagnostic focus.

- [ ] **Step 7: Register the Medusa welcome surface**

`examples/medusa-agent/frontend/src/routedeck/surfaces.tsx` is the sole mapping from compiled component keys to Medusa React components. It contains no routes, transitions, API paths, or policy logic.

- [ ] **Step 8: Run React, core, and welcome consumer tests**

Run:

```powershell
pnpm --filter @routedeck/core test
pnpm --filter @routedeck/react test
pnpm --filter @routedeck/medusa-agent test -- src/tests/app-shell.test.tsx
pnpm typecheck
pnpm build
```

Expected: PASS; old `react/` files can then be removed with equivalent coverage retained.

- [ ] **Step 9: Commit and push Task 10**

```powershell
Invoke-VerifiedTaskStage -TaskFiles $taskFiles
git commit -m "feat: add RouteDeck React primitives"
git push origin saastoagent
```

### Task 11: Replace The Medusa Backend With A Typed Client And Protected Demo Stack

**Files:**
- Complete: `examples/medusa-agent/backend/pyproject.toml` with runtime/client dependencies
- Create: `examples/medusa-agent/backend/medusa_agent/config.py`
- Complete: `examples/medusa-agent/backend/medusa_agent/medusa/client/{protocol,models}.py`
- Create: `examples/medusa-agent/backend/medusa_agent/medusa/client/{http,errors}.py`
- Create: `examples/medusa-agent/backend/tests/unit/client/{test_http,test_delivery_phase,test_endpoint_inventory}.py`
- Create: `examples/medusa-agent/backend/tests/integration/real_medusa/test_store_client.py`
- Create: `examples/medusa-agent/infra/{compose.yaml,demo-manifest.json,medusa-setup.sh,medusa-sentinel.ts,seed-fingerprint.ts}`
- Create: `examples/medusa-agent/scripts/demo-stack.ps1`
- Modify: `.gitignore`
- Modify: `test_targets/medusa-backend/src/scripts/seed.ts` only if deterministic manifest emission requires it

**Interfaces:**
- Consumes: current Medusa 2.13.6 backend/seed source and typed RouteDeck failures.
- Produces: `Settings`, `MedusaStoreClient`, `HttpMedusaStoreClient`, exact Store API models, delivery evidence, and a sentinel-protected dedicated local stack.

- [ ] **Step 1: Write failing client contract and delivery-phase tests**

```python
@pytest.mark.asyncio
async def test_client_sends_publishable_key_only_in_http_adapter() -> None:
    transport = RecordingTransport(json={"products": []})
    client = HttpMedusaStoreClient(settings(), transport=transport)
    await client.list_products(ProductQuery(region_id="reg_1"))
    assert transport.request.headers["x-publishable-api-key"] == "pk_test"


@pytest.mark.parametrize(
    ("failure", "phase"),
    [(ConnectError("dns"), "not_sent"), (ReadTimeout("timeout"), "possibly_sent")],
)
def test_transport_failure_has_typed_delivery_phase(failure: Exception, phase: str) -> None:
    error = classify_transport_failure(failure, request_started=phase != "not_sent")
    assert error.delivery_phase == phase


def test_no_endpoint_literal_exists_outside_http_adapter() -> None:
    assert store_endpoint_inventory(PROJECT_ROOT) == {"medusa/client/http.py": EXPECTED_ENDPOINTS}
```

- [ ] **Step 2: Run client tests and verify RED**

Run: `python -m pytest examples/medusa-agent/backend/tests/unit/client -q`

Expected: FAIL because the typed client package does not exist.

- [ ] **Step 3: Define typed configuration and protocol**

Required configuration has no silent defaults for secrets/IDs:

```python
class Settings(BaseModel):
    medusa_base_url: AnyHttpUrl
    medusa_publishable_key: SecretStr
    medusa_region_id: str
    medusa_sales_channel_id: str
    medusa_payment_provider_id: str
    routedeck_database_path: Path
    routedeck_state_encryption_key: SecretStr
    openai_api_key: SecretStr | None
    openai_model: str
```

The demo manifest supplies `pp_system_default`; runtime verifies that exact ID is returned before enabling payment.

- [ ] **Step 4: Implement protocol models and all Store methods**

```python
class MedusaStoreClient(Protocol):
    async def list_regions(self) -> tuple[Region, ...]: ...
    async def list_products(self, query: ProductQuery) -> ProductPage: ...
    async def get_product(self, handle: str, region_id: str) -> Product: ...
    async def create_cart(self, market: BuyerMarket) -> Cart: ...
    async def get_cart(self, cart_id: str) -> Cart: ...
    async def add_line_item(self, cart_id: str, variant_id: str, quantity: int) -> Cart: ...
    async def update_line_item(self, cart_id: str, line_id: str, quantity: int) -> Cart: ...
    async def remove_line_item(self, cart_id: str, line_id: str) -> Cart: ...
    async def set_checkout_contact(self, cart_id: str, contact: CheckoutContact) -> Cart: ...
    async def list_shipping_options(self, cart_id: str) -> tuple[ShippingOption, ...]: ...
    async def set_shipping_option(self, cart_id: str, option_id: str) -> Cart: ...
    async def list_payment_providers(self, region_id: str) -> tuple[PaymentProvider, ...]: ...
    async def initialize_payment(self, cart: Cart, provider_id: str) -> Cart: ...
    async def complete_cart(self, cart_id: str) -> CompleteCartResult: ...
    async def get_order(self, order_id: str) -> Order: ...
```

Only `http.py` owns URL templates, headers, httpx calls, status/schema validation, and delivery classification. No response-message parsing determines control flow.

- [ ] **Step 5: Build the protected dedicated demo stack**

Use Compose project `routedeck-medusa-demo`, API port `9100`, agent API `8098`, frontend `5198`, internal-only Postgres/Redis, database `routedeck_medusa_demo`, and labeled volumes. `medusa-setup.sh` runs migrations and the real seed exactly once with no `|| true`.

Before any stack command, extend `.gitignore` with the exact generated paths/patterns `examples/medusa-agent/.demo-data/`, `examples/medusa-agent/.env.local`, `examples/medusa-agent/infra/CREDS.generated.*`, `examples/medusa-agent/infra/demo-manifest.generated.json`, `*.sqlite-wal`, `*.sqlite-shm`, and `artifacts/*.json`. Version-controlled templates and `infra/demo-manifest.json` remain tracked; generated secrets never do. Legacy backend `core/`, `routes/`, and `services/` remain untouched and unused until Task 17 removes them after the replacement passes end-to-end tests.

`demo-stack.ps1 -Action Provision` is the only clean-machine bootstrap path. It creates only the exact named Compose project, labeled volumes, database, migrated Medusa schema, deterministic seed, and database sentinel. It performs no deletion. If any same-named resource exists without the expected label/database identity, it fails. If the protected stack already exists, it validates it and exits successfully without reseeding.

After provisioning, `demo-stack.ps1 -Action Reset` must require all of:

```text
compose project == routedeck-medusa-demo
database name == routedeck_medusa_demo
volume label com.routedeck.demo == routedeck-medusa-demo-v1
database sentinel == routedeck-medusa-demo-v1
RouteDeck SQLite path is under examples/medusa-agent/.demo-data
```

Any mismatch stops before deletion. The script never remaps ports or targets another stack.

`infra/demo-manifest.json` version-controls the seed-fingerprint contract: exact allowlisted fields for catalog products/variants, regions, sales channels, shipping options, and enabled payment providers; stable business-key sort order for each collection; and explicit exclusion of generated IDs, timestamps, carts, orders, and volatile metadata. `seed-fingerprint.ts` canonicalizes only that manifest and fails on missing/extra required business fields.

- [ ] **Step 6: Start only the dedicated Medusa services and run real integration**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\demo-stack.ps1 -Action Provision
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\demo-stack.ps1 -Action Reset
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\demo-stack.ps1 -Action Up -Services medusa
python -m pytest examples/medusa-agent/backend/tests/integration/real_medusa/test_store_client.py -q
```

Expected: real products, variants, cart, shipping options, and exact `pp_system_default` provider are returned from `http://127.0.0.1:9100`; no fixture is used.

- [ ] **Step 7: Run client boundaries and stop the probe stack**

Run:

```powershell
python scripts/check_boundaries.py --json artifacts/client-boundary.json
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\demo-stack.ps1 -Action Down
```

Expected: zero endpoint/transport boundary violations; only the dedicated stack stops.

- [ ] **Step 8: Commit and push Task 11**

```powershell
Invoke-VerifiedTaskStage -TaskFiles $taskFiles
git commit -m "feat: add typed Medusa Store client"
git push origin saastoagent
```

### Task 12: Deliver Catalog Browse, Product Detail, Variant Selection, And Public Deep Links

**Files:**
- Create: `examples/medusa-agent/backend/medusa_agent/features/catalog/{models,providers,handlers}.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/features/catalog/feature.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/composition.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/api/health.py`
- Modify: `examples/medusa-agent/backend/main.py`
- Create: `examples/medusa-agent/backend/tests/unit/features/test_catalog.py`
- Create: `examples/medusa-agent/backend/tests/contract/test_catalog_projection.py`
- Create: `examples/medusa-agent/backend/tests/integration/real_medusa/test_catalog_flow.py`
- Modify: `examples/medusa-agent/backend/tests/support/{medusa,runtime}.py`
- Create: `examples/medusa-agent/frontend/src/features/catalog/{ProductGridSurface,ProductDetailSurface,ProductCard,VariantSelector}.tsx`
- Create: `examples/medusa-agent/frontend/src/tests/{catalog-flow,network-boundary}.test.tsx`
- Create: `examples/medusa-agent/frontend/src/tests/support/buyer.tsx`
- Modify: `examples/medusa-agent/frontend/src/routedeck/surfaces.tsx`

**Interfaces:**
- Consumes: typed Store client, compiled app, session/projection, FastAPI router, frontend store/React host.
- Produces: `CatalogProvider`, catalog handlers, real product/variant observations, allowlists, product-grid/detail surfaces, and `/products/{product_handle}` public links.

- [ ] **Step 1: Write failing backend catalog tests**

```python
@pytest.mark.asyncio
async def test_catalog_list_projects_real_products_and_variant_bindings() -> None:
    client = StubMedusaStoreClient(products=(product("t-shirt", variants=(variant("variant_1"),)),))
    result = await run_catalog_list(app_with(client), session_at("buyer.home"))
    assert result.projection.graph_node == "catalog.browse"
    assert result.projection.presentation_state["products"][0]["handle"] == "t-shirt"
    assert result.session.private_state.entity_allowlists["catalog.select_variant"] == {"variant_1"}


@pytest.mark.asyncio
async def test_open_product_navigation_reads_detail_once() -> None:
    client = CountingMedusaStoreClient(product=product("t-shirt"))
    await dispatch("catalog.open_product", {"product_handle": "t-shirt"}, client=client)
    assert client.calls("get_product") == 1
```

- [ ] **Step 2: Write failing frontend catalog tests**

```tsx
it("opens a projected product through the supervised surface event", async () => {
  renderBuyer(projectionWithProducts())
  await user.click(screen.getByRole("link", { name: /medusa t-shirt/i }))
  expect(routeDeck.dispatch).toHaveBeenCalledWith(expect.objectContaining({ operationId: "catalog.open_product" }))
  expect(fetchSpy).not.toHaveBeenCalledWith(expect.stringContaining("/store/"), expect.anything())
})
```

- [ ] **Step 3: Run catalog tests and verify RED**

Run:

```powershell
python -m pytest examples/medusa-agent/backend/tests/unit/features/test_catalog.py examples/medusa-agent/backend/tests/contract/test_catalog_projection.py -q
pnpm --filter @routedeck/medusa-agent test -- src/tests/catalog-flow.test.tsx
```

Expected: FAIL because catalog bindings and surfaces do not exist.

- [ ] **Step 4: Implement catalog provider/handlers and bind them once**

`catalog.list` and `catalog.search` call the typed client and return authoritative observations. `catalog.open_product` is navigation-only and lets the destination provider read detail exactly once. `catalog.select_variant` validates the current operation allowlist and updates RouteDeck selection state without a Medusa write.

- [ ] **Step 5: Implement product surfaces and public route handling**

Components render only projection props. `ProductCard` uses `RouteDeckLink` and a supervised open operation. `VariantSelector` emits the declared entity key; it never sees or constructs arbitrary API arguments. The browser route codec round-trips `/products/t-shirt` without regex.

- [ ] **Step 6: Mount the application and run real catalog integration**

`main.py` mounts product-owned `/api/medusa-agent/health` and the generic RouteDeck router. Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\demo-stack.ps1 -Action Up -Services medusa
python -m pytest examples/medusa-agent/backend/tests/integration/real_medusa/test_catalog_flow.py -q
pnpm --filter @routedeck/medusa-agent test -- src/tests/catalog-flow.test.tsx src/tests/network-boundary.test.tsx
```

Expected: catalog facts come from real Medusa and frontend network evidence contains zero `/store/*` requests.

- [ ] **Step 7: Commit and push Task 12**

```powershell
Invoke-VerifiedTaskStage -TaskFiles $taskFiles
git commit -m "feat: add Medusa catalog buyer slice"
git push origin saastoagent
```

### Task 13: Deliver Journaled Cart Creation And Real Cart Mutation

**Files:**
- Create: `examples/medusa-agent/backend/medusa_agent/features/cart/{models,providers,guards,handlers}.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/features/cart/feature.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/composition.py`
- Create: `examples/medusa-agent/backend/tests/unit/features/test_cart.py`
- Create: `examples/medusa-agent/backend/tests/contract/test_cart_supervision.py`
- Create: `examples/medusa-agent/backend/tests/integration/real_medusa/test_cart_flow.py`
- Modify: `examples/medusa-agent/backend/tests/support/{medusa,runtime}.py`
- Create: `examples/medusa-agent/frontend/src/features/cart/{CartSummarySurface,CartLineItem}.tsx`
- Create: `examples/medusa-agent/frontend/src/tests/cart-flow.test.tsx`
- Modify: `examples/medusa-agent/frontend/src/routedeck/surfaces.tsx`

**Interfaces:**
- Consumes: real selected variant binding, operation runner, SQLite store, Store client, and cart surface registry.
- Produces: `cart.create`, `cart.add_item`, `cart.open`, `cart.update_item`, `cart.remove_item`, authoritative cart projection, and line-item allowlists.

- [ ] **Step 1: Write failing cart supervision tests**

```python
@pytest.mark.asyncio
async def test_cart_is_created_as_a_separate_journaled_attempt() -> None:
    result = await initialize_buyer_session(app)
    assert result.session.private_state.cart_ref is not None
    assert [attempt.operation_id for attempt in await store.attempts(result.session_id)] == ["cart.create"]


@pytest.mark.asyncio
async def test_add_item_rejects_unseen_variant_before_store_call() -> None:
    client = CountingMedusaStoreClient()
    result = await dispatch("cart.add_item", {"entity_key": "forged", "quantity": 1}, client=client)
    assert result.failure.code == "entity_not_allowed"
    assert client.calls("add_line_item") == 0


@pytest.mark.asyncio
async def test_duplicate_request_id_does_not_add_twice() -> None:
    first = await add_item(request_id="add-1")
    replay = await add_item(request_id="add-1")
    assert replay == first
    assert client.calls("add_line_item") == 1
```

- [ ] **Step 2: Run cart tests and verify RED**

Run:

```powershell
python -m pytest examples/medusa-agent/backend/tests/unit/features/test_cart.py examples/medusa-agent/backend/tests/contract/test_cart_supervision.py -q
pnpm --filter @routedeck/medusa-agent test -- src/tests/cart-flow.test.tsx
```

Expected: FAIL because cart bindings and components do not exist.

- [ ] **Step 3: Implement cart feature bindings**

New-session initialization calls `cart.create` through the runner with typed market configuration. `cart.add_item` requires the stored cart ref and current variant allowlist. Update/remove require current line-item allowlists from the last authoritative cart observation. No handler creates a cart as fallback.

- [ ] **Step 4: Implement cart projection and UI**

Project display-safe item titles, selected options, quantity, unit/line totals, currency, subtotal, shipping/tax/total when returned, and opaque RouteDeck entity keys. Cart components dispatch only compiled operations and render updated authoritative projections after each call.

- [ ] **Step 5: Test uncertain cart creation explicitly**

Fault-inject `not_sent` and `possibly_sent` into `cart.create`. The first permits an explicit retry; the second blocks further cart creation in that session and projects a recovery error. Neither path silently creates or substitutes a cart.

- [ ] **Step 6: Run real Medusa cart flow and frontend regression**

Run:

```powershell
python -m pytest examples/medusa-agent/backend/tests/integration/real_medusa/test_cart_flow.py -q
pnpm --filter @routedeck/medusa-agent test -- src/tests/catalog-flow.test.tsx src/tests/cart-flow.test.tsx
```

Expected: real cart ID is private, quantities/totals match Store API, and add/update/remove each execute once.

- [ ] **Step 7: Commit and push Task 13**

```powershell
Invoke-VerifiedTaskStage -TaskFiles $taskFiles
git commit -m "feat: add supervised Medusa cart slice"
git push origin saastoagent
```

### Task 14: Deliver Encrypted Contact And Real Shipping Selection

**Files:**
- Create: `examples/medusa-agent/backend/medusa_agent/features/checkout/{models,providers,guards,handlers}.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/features/checkout/feature.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/composition.py`
- Create: `examples/medusa-agent/backend/tests/unit/features/{test_contact,test_shipping}.py`
- Create: `examples/medusa-agent/backend/tests/contract/test_checkout_privacy.py`
- Create: `examples/medusa-agent/backend/tests/integration/real_medusa/test_delivery_flow.py`
- Modify: `examples/medusa-agent/backend/tests/support/{medusa,runtime}.py`
- Create: `examples/medusa-agent/frontend/src/features/checkout/{ContactFormSurface,ShippingOptionsSurface}.tsx`
- Create: `examples/medusa-agent/frontend/src/tests/{contact-flow,delivery-payment-flow}.test.tsx`
- Modify: `examples/medusa-agent/frontend/src/routedeck/surfaces.tsx`

**Interfaces:**
- Consumes: active cart, private-form API, Store client, returned shipping options, and checkout nodes.
- Produces: `checkout.start`, `checkout.save_contact`, `checkout.select_shipping`, encrypted contact/shipping/billing draft, shipping allowlists, and contact/delivery surfaces.

- [ ] **Step 1: Write failing privacy and delivery tests**

```python
@pytest.mark.asyncio
async def test_contact_never_enters_projection_events_or_model_context() -> None:
    contact = checkout_contact(
        email="buyer@example.test",
        shipping_address_1="1 Test Street",
        billing_choice="same_as_shipping",
    )
    await private_forms.save(session_id, "contact", contact.model_dump())
    await dispatch("checkout.save_contact", {"form_handle": "contact"})
    combined = projection_json() + event_json() + model_context_json()
    assert "buyer@example.test" not in combined
    assert "1 Test Street" not in combined


@pytest.mark.asyncio
async def test_separate_billing_address_is_required_and_private() -> None:
    contact = checkout_contact(billing_choice="separate", billing_address=None)
    result = await save_contact(contact)
    assert result.failure.code == "billing_address_required"
    assert client.calls("set_checkout_contact") == 0


@pytest.mark.asyncio
async def test_shipping_accepts_only_returned_option() -> None:
    await load_shipping_options((shipping_option("ship_standard"),))
    result = await dispatch("checkout.select_shipping", {"entity_key": "forged"})
    assert result.failure.code == "entity_not_allowed"
    assert client.calls("set_shipping_option") == 0
```

- [ ] **Step 2: Run checkout tests and verify RED**

Run:

```powershell
python -m pytest examples/medusa-agent/backend/tests/unit/features/test_contact.py examples/medusa-agent/backend/tests/unit/features/test_shipping.py examples/medusa-agent/backend/tests/contract/test_checkout_privacy.py -q
pnpm --filter @routedeck/medusa-agent test -- src/tests/contact-flow.test.tsx src/tests/delivery-payment-flow.test.tsx
```

Expected: FAIL because private checkout bindings and surfaces do not exist.

- [ ] **Step 3: Implement structured private contact flow**

The form validates email, name, phone, shipping address lines, city, province, postal code, and country code structurally. It requires a typed billing choice of `same_as_shipping` or `separate`; the latter requires a separately validated billing address inside the same encrypted blob. `checkout.save_contact` receives only an opaque form handle, loads decrypted values server-side, calls `set_checkout_contact` so the Medusa cart receives email plus shipping/billing addresses, records only public completion flags, and transitions to delivery. The model sees completeness/validation status only.

- [ ] **Step 4: Implement real shipping provider and selection**

Entry to `checkout.delivery` calls `list_shipping_options(cart_id)`, binds exact returned IDs, and projects display-safe labels/prices. Selection calls `set_shipping_option` once, refreshes the cart observation, and moves to payment. Missing options is a visible business failure with payment disabled.

- [ ] **Step 5: Implement contact and shipping surfaces**

`ContactFormSurface` uses `RouteDeckPrivateForm`; values and the conditional separate billing address remain in memory and the no-store channel. Dirty back/cancel follows compiled policy. `ShippingOptionsSurface` renders only projection options and dispatches their entity keys.

- [ ] **Step 6: Run real delivery flow and privacy scans**

Run:

```powershell
python -m pytest examples/medusa-agent/backend/tests/integration/real_medusa/test_delivery_flow.py examples/medusa-agent/backend/tests/contract/test_checkout_privacy.py -q
pnpm --filter @routedeck/medusa-agent test -- src/tests/contact-flow.test.tsx src/tests/delivery-payment-flow.test.tsx
```

Expected: real Medusa cart contains the address and selected shipping method; proof output/logs contain neither raw value.

- [ ] **Step 7: Commit and push Task 14**

```powershell
Invoke-VerifiedTaskStage -TaskFiles $taskFiles
git commit -m "feat: add private delivery checkout slice"
git push origin saastoagent
```

### Task 15: Deliver System Payment, Reviewed Placement, And Verified Confirmation

**Files:**
- Modify: `examples/medusa-agent/backend/medusa_agent/features/checkout/{feature,providers,guards,handlers,models}.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/features/orders/feature.py`
- Create: `examples/medusa-agent/backend/medusa_agent/features/orders/{models,providers,handlers}.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/composition.py`
- Create: `examples/medusa-agent/backend/tests/unit/features/{test_payment,test_review,test_orders}.py`
- Create: `examples/medusa-agent/backend/tests/contract/test_place_order_safety.py`
- Create: `examples/medusa-agent/backend/tests/integration/real_medusa/test_order_flow.py`
- Modify: `examples/medusa-agent/backend/tests/support/{medusa,runtime}.py`
- Create: `examples/medusa-agent/frontend/src/features/checkout/{PaymentMethodSurface,OrderReviewSurface}.tsx`
- Create: `examples/medusa-agent/frontend/src/features/orders/OrderConfirmationSurface.tsx`
- Create: `examples/medusa-agent/frontend/src/tests/{review-flow,confirmation-flow}.test.tsx`
- Modify: `examples/medusa-agent/frontend/src/routedeck/surfaces.tsx`

**Interfaces:**
- Consumes: real cart/address/shipping facts, configured provider, durable review runner, and Store completion/order APIs.
- Produces: `checkout.select_payment`, `checkout.place_order`, `catalog.continue_shopping`, payment/review/recovery/confirmation surfaces, and independently verified order projection.

- [ ] **Step 1: Write failing provider and review tests**

```python
@pytest.mark.asyncio
async def test_only_exact_configured_system_provider_is_enabled() -> None:
    client.providers = (provider("pp_system_default"), provider("pp_stripe_test"))
    result = await enter_payment()
    assert result.projection.presentation_state["payment_providers"] == [
        {"entity_key": ANY, "label": "System / manual demo payment"}
    ]


@pytest.mark.asyncio
async def test_reject_and_stale_review_never_complete_cart() -> None:
    review = await propose_place_order()
    await reject(review)
    stale = await propose_place_order()
    await mutate_cart_total()
    result = await accept(stale)
    assert result.failure.code == "review_stale"
    assert client.calls("complete_cart") == 0


@pytest.mark.asyncio
async def test_confirmation_requires_order_result_and_independent_reread() -> None:
    client.complete_result = order_result("order_1")
    client.order = order("order_1", items=(order_item("variant_1", 1),))
    result = await approve_place_order()
    assert result.projection.graph_node == "orders.confirmation"
    assert client.calls("complete_cart") == 1
    assert client.calls("get_order") == 1
```

- [ ] **Step 2: Run payment/order tests and verify RED**

Run:

```powershell
python -m pytest examples/medusa-agent/backend/tests/unit/features/test_payment.py examples/medusa-agent/backend/tests/unit/features/test_review.py examples/medusa-agent/backend/tests/unit/features/test_orders.py examples/medusa-agent/backend/tests/contract/test_place_order_safety.py -q
pnpm --filter @routedeck/medusa-agent test -- src/tests/review-flow.test.tsx src/tests/confirmation-flow.test.tsx
```

Expected: FAIL because payment/review/order bindings and surfaces are incomplete.

- [ ] **Step 3: Implement exact provider validation and initialization**

Entry provider reads real returned providers. Enable only `Settings.medusa_payment_provider_id`; fail if absent. The handler initializes one payment session, refreshes cart/payment facts, and transitions to review. UI visibly labels it demo/manual and collects no card data.

- [ ] **Step 4: Implement frozen reviewed order placement**

The public review projection contains display-safe items, quantities, shipping option, currency, totals, and contact/billing completeness only. The review form slot hydrates the buyer's address summary separately through the authenticated no-store private-form channel; no address value enters projection, SSE, model context, diagnostics, or ordinary traces. Approval refreshes cart and fingerprints totals/inventory/shipping/payment before the runner calls complete-cart once.

```python
match await client.complete_cart(cart_id):
    case OrderPlaced(order=order):
        verified = await client.get_order(order.id)
        return validate_order_against_review(verified, frozen_review)
    case CartCompletionRejected(error=error):
        return OperationOutcome.business_failure(code=error.code, message=error.message)
```

Any invalid response after send becomes `external_outcome_unknown`; it never matches a success case.

- [ ] **Step 5: Implement unknown-completion and confirmation surfaces**

Unknown state stays on review, disables placement through restart, and renders “Order status could not be confirmed; do not submit again.” Reconciliation can succeed only through a product handler that obtains and re-reads an actual Medusa order matching the frozen review. Confirmation renders only that verified projection.

- [ ] **Step 6: Run the real full Store API order integration**

Run: `python -m pytest examples/medusa-agent/backend/tests/integration/real_medusa/test_order_flow.py -q`

Expected: review rejection invokes complete-cart zero times; approval invokes it once; result is `type: "order"`; re-read order matches items, quantities, totals, email, shipping, and `pp_system_default` evidence.

- [ ] **Step 7: Run frontend review/confirmation tests**

Run: `pnpm --filter @routedeck/medusa-agent test -- src/tests/review-flow.test.tsx src/tests/confirmation-flow.test.tsx`

Expected: PASS; no `type: "cart"`, malformed response, or unknown outcome can render confirmation.

- [ ] **Step 8: Commit and push Task 15**

```powershell
Invoke-VerifiedTaskStage -TaskFiles $taskFiles
git commit -m "feat: complete reviewed Medusa checkout"
git push origin saastoagent
```

### Task 16: Integrate The LangGraph Buyer Agent And Separate Chat Stream

**Files:**
- Complete: `examples/medusa-agent/backend/medusa_agent/agent.py`
- Create: `examples/medusa-agent/backend/medusa_agent/api/chat.py`
- Modify: `examples/medusa-agent/backend/main.py`
- Create: `examples/medusa-agent/backend/tests/unit/test_agent.py`
- Create: `examples/medusa-agent/backend/tests/contract/test_full_agent_flow.py`
- Create: `examples/medusa-agent/backend/tests/contract/{test_chat_state_convergence,test_no_heuristic_routing}.py`
- Create: `examples/medusa-agent/backend/tests/live/test_real_model_smoke.py`
- Modify: `examples/medusa-agent/backend/tests/support/runtime.py`
- Create: `examples/medusa-agent/frontend/src/app/{chatClient,useAgentStream}.ts`
- Create: `examples/medusa-agent/frontend/src/ui/{AgentShell,Conversation,Composer}.tsx`
- Create: `examples/medusa-agent/frontend/src/tests/agent-flow.test.tsx`
- Modify: `routedeck_testing/scripted_model.py`

**Interfaces:**
- Consumes: Medusa feature bindings, LangGraph middleware, RouteDeck-owned history, real/configured model, operation runner, and compiled surface contract.
- Produces: the existing injected `create_medusa_agent`, `create_live_medusa_agent`, product-owned `/api/medusa-agent/chat`, assistant SSE, test-only scripted-model flow, and real-model smoke.

- [ ] **Step 1: Write failing scripted-agent and convergence tests**

```python
@pytest.mark.asyncio
async def test_scripted_agent_changes_state_only_through_tools() -> None:
    model = ScriptedToolModel([
        tool_call("catalog.list", {}),
        tool_call("catalog.open_product", {"product_handle": "t-shirt"}),
    ])
    result = await chat(model=model, message="show me a shirt")
    assert result.session.current.node_id == "catalog.product"
    assert [attempt.source for attempt in result.attempts] == ["agent", "agent"]


@pytest.mark.asyncio
async def test_assistant_prose_does_not_patch_projection() -> None:
    model = ScriptedTextModel("I added it to your cart")
    before = await store.load(session_id)
    await chat(model=model, message="add it")
    after = await store.load(session_id)
    assert after.projection_version == before.projection_version


@pytest.mark.asyncio
async def test_scripted_agent_and_private_surface_complete_one_buyer_flow() -> None:
    flow = await run_scripted_buyer_until_review()
    assert flow.session.current.node_id == "checkout.review"
    assert flow.private_contact_source == "surface"
    assert flow.review.disposition == "requires_review"
    confirmed = await flow.runtime.runner.accept_review(
        flow.review.id,
        request_id="agent-approve-1",
        expected_session_version=flow.session.session_version,
    )
    assert confirmed.projection.graph_node == "orders.confirmation"
    assert flow.client.calls("complete_cart") == 1
    assert flow.client.calls("get_order") == 1
```

- [ ] **Step 2: Run agent tests and verify RED**

Run:

```powershell
python -m pytest examples/medusa-agent/backend/tests/unit/test_agent.py examples/medusa-agent/backend/tests/contract/test_chat_state_convergence.py examples/medusa-agent/backend/tests/contract/test_no_heuristic_routing.py -q
```

Expected: FAIL because the new agent composition does not exist.

- [ ] **Step 3: Implement product-owned agent composition**

```python
def create_medusa_agent(*, model: BaseChatModel, runtime: RouteDeckRuntime):
    return create_agent(
        model=model,
        tools=runtime.langgraph_tools(),
        middleware=[RouteDeckMiddleware(runtime)],
        system_prompt=BUYER_AGENT_PROMPT,
    )


def create_live_medusa_agent(settings: Settings, runtime: RouteDeckRuntime):
    if settings.openai_api_key is None:
        raise MissingModelCredential("OPENAI_API_KEY is required for the live agent")
    model = ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key.get_secret_value())
    return create_medusa_agent(model=model, runtime=runtime)
```

The Medusa prompt/personality lives here. Tool schemas come from compiled operations. There is no keyword table, regex router, command map, or canned assistant fallback.

- [ ] **Step 4: Persist conversation through RouteDeck, not LangGraph memory**

Each request reconstructs LangGraph messages from RouteDeck-owned finalized conversation/tool observations, acquires one RouteDeck parent turn lease with the request's expected session version, and runs structured tool calls serially as child attempts under that lease. Review staging commits and releases the turn. Stream partial tokens to assistant SSE but call `RouteDeckOperationRunner.complete_turn` only after model completion. Cancellation/process recovery calls `interrupt_turn`, which marks `turn_interrupted`; it does not treat partial prose as final or repeat a journaled tool result. Product code never writes conversation/session tables directly.

- [ ] **Step 5: Implement product chat API and frontend conversation shell**

`POST /api/medusa-agent/chat` accepts a session-authenticated message, globally unique request ID, and expected session version, then returns assistant SSE only. RouteDeck state/projection events remain on `/api/routedeck/events`. `AgentShell` renders conversation and the active product surface in chronology, not in a detached side panel.

- [ ] **Step 6: Run scripted backend/frontend flow**

Run:

```powershell
python -m pytest examples/medusa-agent/backend/tests/unit/test_agent.py examples/medusa-agent/backend/tests/contract -q
pnpm --filter @routedeck/medusa-agent test -- src/tests/agent-flow.test.tsx
```

Expected: PASS; every claimed state change has matching supervised attempt and projection evidence. The scripted full flow uses agent tools for discovery/cart/checkout decisions, the private surface for contact and billing data, and the internal RouteDeck review control for final approval; no model sees private form values.

- [ ] **Step 7: Run configured real-model smoke or record the explicit blocker**

Run: `python -m pytest examples/medusa-agent/backend/tests/live/test_real_model_smoke.py -q -m live_model`

Expected: PASS only with a configured real key/model and structured catalog state change. Missing credentials must fail as `MissingModelCredential`; it may not skip and may not use the scripted model.

- [ ] **Step 8: Commit and push Task 16**

```powershell
Invoke-VerifiedTaskStage -TaskFiles $taskFiles
git commit -m "feat: add LangGraph Medusa buyer agent"
git push origin saastoagent
```

### Task 17: Prove Reload, Replay, Deep Links, Recovery, And Full Browser Flow

**Files:**
- Create: `examples/medusa-agent/frontend/src/app/{App,config}.tsx`
- Create: `examples/medusa-agent/frontend/src/ui/{BuyerNavigation,RouteDeckStatusRail}.tsx`
- Create: `examples/medusa-agent/frontend/src/tests/full-buyer-flow.test.tsx`
- Create: `examples/medusa-agent/frontend/playwright.config.ts`
- Create: `examples/medusa-agent/e2e/{buyer-flow,agent-buyer-flow,deep-links,reconnect,recovery,network-boundary}.spec.ts`
- Create: `examples/medusa-agent/e2e/support/buyer-flow.ts`
- Create: `examples/medusa-agent/backend/tests/contract/test_restart_recovery.py`
- Modify: `examples/medusa-agent/infra/compose.yaml`
- Remove: old `examples/medusa-agent/frontend/src/App.tsx`, `App.test.tsx`, hooks, and old styles after replacement tests pass

**Interfaces:**
- Consumes: complete backend/frontend, durable session/event store, demo stack, scripted model, and real Medusa.
- Produces: runnable full local app and deterministic Chromium evidence for all non-live-model browser requirements.

- [ ] **Step 1: Write failing Playwright flow and network assertions**

```ts
test("completes the full guest buyer flow", async ({ page }) => {
  await page.goto("http://127.0.0.1:5198/")
  await page.getByRole("button", { name: "Browse products" }).click()
  await page.getByRole("link", { name: /Medusa T-Shirt/i }).click()
  await page.getByLabel("Size").selectOption("M")
  await page.getByRole("button", { name: "Add to cart" }).click()
  await page.getByRole("link", { name: "Cart" }).click()
  await page.getByRole("button", { name: "Checkout" }).click()
  await fillPrivateContact(page)
  await page.getByRole("radio", { name: /Standard Shipping/i }).check()
  await page.getByRole("radio", { name: /System.*manual demo/i }).check()
  await page.getByRole("button", { name: "Review order" }).click()
  await page.getByRole("button", { name: "Place order" }).click()
  await expect(page.getByText("Approval required")).toBeVisible()
  await page.getByRole("button", { name: "Approve order" }).click()
  await expect(page.getByRole("heading", { name: "Order confirmed" })).toBeVisible()
})

test("browser never calls Medusa Store API", async ({ page }) => {
  const storeRequests: string[] = []
  page.on("request", request => { if (request.url().includes("/store/")) storeRequests.push(request.url()) })
  await runBuyerFlow(page)
  expect(storeRequests).toEqual([])
})
```

- [ ] **Step 2: Run Playwright tests and verify RED**

Run: `pnpm --filter @routedeck/medusa-agent exec playwright test e2e/buyer-flow.spec.ts`

Expected: FAIL because the final app shell/compose integration is incomplete.

- [ ] **Step 3: Complete app shell and local compose services**

Compose starts dedicated Medusa on `9100`, RouteDeck/Medusa backend on `8098`, and frontend on `5198`. Vite proxies `/api` to backend; only backend reaches Medusa. Health checks fail loudly and no port remapping occurs.

- [ ] **Step 4: Add deep-link, history, reload, and SSE scenarios**

Prove shareable `/products/t-shirt`, session-required cart/checkout/review/confirmation links, rejection of missing/expired/cross-session resume capabilities, browser back/forward/cancel, reload at cart/review/confirmation, cursor replay, duplicate suppression, forced gap resync, and expired cursor reset. No scenario dispatches an operation during resync.

`agent-buyer-flow.spec.ts` repeats the real-Medusa guest flow with the explicitly test-only scripted model: chat/tool calls drive catalog, variant, cart, shipping, payment, and order proposal; the browser private form supplies contact/billing data; the user approves through the RouteDeck review primitive; confirmation still requires the one real complete-cart call and independent order re-read.

- [ ] **Step 5: Add concurrent-tab and restart crash scenarios**

Prove stale version conflict between two tabs, session isolation between different cookies, review state after backend restart, result-journal crash recovery with zero additional handler calls, post-commit/pre-assistant crash recovery, and unknown complete-cart remaining disabled after restart.

- [ ] **Step 6: Run component, backend, and Chromium suites**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\demo-stack.ps1 -Action Provision
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\demo-stack.ps1 -Action Reset
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\demo-stack.ps1 -Action Up -Services all
python -m pytest examples/medusa-agent/backend/tests/contract/test_restart_recovery.py -q
pnpm --filter @routedeck/medusa-agent test
pnpm --filter @routedeck/medusa-agent exec playwright test
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\demo-stack.ps1 -Action Down
```

Expected: all health checks pass at `http://127.0.0.1:9100`, `http://127.0.0.1:8098`, and `http://127.0.0.1:5198`; Chromium desktop and the configured narrow viewport PASS; `Down` stops only the labeled dedicated stack. The final E2E runner uses `try/finally` so test failure still executes that scoped `Down` action.

- [ ] **Step 7: Remove the replaced implementation and rerun boundaries**

Remove old backend `core/`, `routes/`, `services/`, legacy slice tests, old frontend hooks/monolith, npm lockfiles, process-local event bus, handwritten projection/router, and `InMemorySaver`. Keep only explicitly migrated behavioral evidence. Run `python scripts/check_boundaries.py` and ensure zero old product path or fallback remains.

- [ ] **Step 8: Commit and push Task 17**

```powershell
Invoke-VerifiedTaskStage -TaskFiles $taskFiles
git commit -m "feat: complete RouteDeck Medusa browser flow"
git push origin saastoagent
```

### Task 18: Enforce Release Gates, Generate Proof, And Finish Documentation

**Files:**
- Create: `tests/test_release_harness.py`
- Create: `scripts/check_critical_coverage.py`
- Create: `.coveragerc`
- Create: `examples/medusa-agent/scripts/release-verify.ps1`
- Create: `examples/medusa-agent/scripts/release-summary.py`
- Modify: `.gitignore`
- Modify: `README.md`
- Replace: `examples/medusa-agent/README.md`
- Modify: `architecture/code-map.md`
- Modify: `test_index/README.md`
- Modify: `structure.md`
- Modify: `docs/route-deck-reference.md`
- Modify: `docs/medusa-agent-reference-app.md`
- Create/update: `artifacts/release/.gitkeep` only; generated run bundles stay ignored

**Interfaces:**
- Consumes: all test lanes, protected demo reset/fingerprint, boundary/schema reports, real order proof, Playwright trace, and live-model smoke.
- Produces: one fail-loud local verifier and the exact sanitized release bundle required by the design.

- [ ] **Step 1: Write failing release-harness contract tests**

```python
def test_critical_coverage_groups_are_explicit() -> None:
    config = load_coverage_config()
    assert set(config.groups) == {
        "state", "navigation", "supervision", "projection", "persistence", "event_reducer"
    }
    assert all(group.branch_threshold == 85 for group in config.groups.values())


def test_release_summary_requires_every_gate() -> None:
    with pytest.raises(IncompleteReleaseEvidence):
        build_release_summary(gate_results={"framework": "pass"})


def test_release_gate_names_match_the_approved_design() -> None:
    assert REQUIRED_GATES == (
        "framework_correctness",
        "boundary_and_adapter_integrity",
        "real_commerce_source_of_truth",
        "browser_agent_and_developer_experience",
    )
```

- [ ] **Step 2: Run release-harness tests and verify RED**

Run: `python -m pytest tests/test_release_harness.py -q`

Expected: FAIL because coverage grouping and summary validation do not exist.

- [ ] **Step 3: Implement executable coverage, schema, boundary, and proof gates**

`check_critical_coverage.py` reads version-controlled globs and enforces 85% branch coverage independently. Boundary report combines Python import AST, endpoint inventory, product-source regex/keyword/fixture scans with explicit allowlists, frontend captured network traffic, and an architectural review result. Expected violation count is zero.

- [ ] **Step 4: Finish developer documentation and define clean-install proof**

Document package boundaries, feature authoring, standard middleware and raw ToolNode integration, session/persistence model, private forms, local demo stack, exact URLs (`5198`, `8098`, `9100`), provision/reset safety, failure modes, and how to interpret proof artifacts. Define the executable quickstart and a fresh-install lane using a new Python venv plus an isolated pnpm store/cache; these commands must be complete before the verifier captures their output.

- [ ] **Step 5: Implement the fail-loud release verifier**

`release-verify.ps1`:

1. validates local tool versions, required real-model credentials, configured ports, and encryption key without printing secrets;
2. provisions or validates the dedicated stack without deletion, then performs the sentinel-protected reset and captures the manifest-normalized seed fingerprint;
3. runs Python unit/contract/conformance/integration tests plus grouped branch coverage;
4. runs pnpm contract generation, schema parity, tests, typecheck, and build;
5. starts the complete local stack and runs scripted-model Playwright, restart/replay/unknown-outcome scenarios, and real-model smoke;
6. records the one approved complete-cart call and independent order re-read;
7. resets again and proves test-created records absent plus seed fingerprint equality;
8. runs the documented quickstart and fresh Python/pnpm install lanes in isolated directories and captures their sanitized logs;
9. writes sanitized artifacts and stops only the dedicated stack.

Any failure stops the gate and marks the summary failed. Cleanup is explicit in `finally`; it never changes to another provider, model, port, database, or host.

- [ ] **Step 6: Generate the exact proof bundle**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\release-verify.ps1
```

Expected bundle:

```text
artifacts/release/<utc-run-id>/
  RELEASE_SUMMARY.md
  gate-results.json
  environment.json
  commands.jsonl
  junit/
  coverage/
  contracts/
    compiled-navgraph.json
    frontend-contract.json
    executable-test-paths.json
    schema-parity.json
    conformance-results.json
    boundary-report.json
  medusa/
    seed-before.json
    store-api-trace.ndjson
    order-proof.json
    seed-after-reset.json
  runtime/
    supervision-trace.ndjson
    sse-trace.ndjson
    persistence-restart.json
  browser/
    playwright-report/
    full-flow-trace.zip
    browse.png
    cart.png
    review-pending.png
    confirmation.png
    network-boundary.json
  docs/
    clean-install.txt
    quickstart-smoke.txt
```

PII/private-ID correlation uses per-run keyed HMAC with the key excluded; otherwise record booleans. No raw PII, secrets, private IDs, or response bodies enter artifacts.

- [ ] **Step 7: Run final complete verification**

Run:

```powershell
python -m pytest tests examples/medusa-agent/backend/tests -q
python -m ruff check routedeck_core routedeck_langgraph routedeck_fastapi routedeck_sqlite routedeck_testing examples/medusa-agent/backend tests
python -m ruff format --check routedeck_core routedeck_langgraph routedeck_fastapi routedeck_sqlite routedeck_testing examples/medusa-agent/backend tests
python -m mypy routedeck_core routedeck_langgraph routedeck_fastapi routedeck_sqlite routedeck_testing examples/medusa-agent/backend/medusa_agent
python -m build
pnpm test
pnpm typecheck
pnpm build
python scripts/check_doc_coverage.py
python scripts/check_boundaries.py --json artifacts/final-boundary-report.json
```

Expected: every command PASS; critical groups each meet 85% branch coverage; real-model and real-order gates pass; no fallback or direct Store API frontend traffic exists.

- [ ] **Step 8: Commit and push Task 18**

```powershell
Invoke-VerifiedTaskStage -TaskFiles $taskFiles
git commit -m "docs: publish RouteDeck Medusa release proof"
git push origin saastoagent
```

## Mandatory Negative-Case Ownership

| Negative case | Owning task and executable test lane |
|---|---|
| Missing encryption, Medusa IDs/credentials, or model credential | Tasks 6, 11, 16; SQLite startup, `Settings`, and live-model tests |
| Unavailable/unauthorized Medusa and malformed typed responses | Task 11; HTTP adapter unit and real-client contract tests |
| Typed `not_sent`, `possibly_sent`, and `response_received` write evidence | Tasks 5, 11, 13, 15; crash-window and client-classification tests |
| Invalid routes or missing/cross-session deep-link capability | Tasks 3-4, 7, 9, 17; route compiler, transport, store, and Playwright tests |
| Stale version, conflicting active attempt, duplicate dispatch, and request-ID reuse | Tasks 5-6, 13, 17; runner, CAS, cart, and concurrent-tab tests |
| Raw/private entity-ID injection and forged product/variant/line/shipping/payment/order handles | Tasks 5, 12-15; guard and feature contract tests |
| Unavailable variant, empty/missing cart, invalid contact, absent shipping, or absent configured provider | Tasks 12-15; feature unit and real-Medusa integration tests |
| Changed cart after review, rejection, expiry, stale review, and approval replay | Tasks 5 and 15; review lifecycle and place-order safety tests |
| Structured `type: "cart"`, malformed completion, ambiguous completion, and attempted second completion | Tasks 15 and 17; order safety, restart, and browser recovery tests |
| Unknown surface, event duplicate/gap/expired cursor, and resync without product dispatch | Tasks 7, 9-10, 17; SSE, reducer, surface-host, and reconnect tests |
| Restart during review, external execution, journaled-result application, assistant finalization, or unknown outcome | Tasks 5-6, 16-17; crash-window, persistence, agent-history, and restart tests |

Task 18 fails the release if any row lacks a passing result in `gate-results.json`; no row may be marked not-applicable for this release.

## Spec Coverage Matrix

| Approved design requirement | Implementation tasks | Release evidence |
|---|---:|---|
| Objective, approved strategy, and RouteDeck/Medusa ownership boundary | 1-2 | ADR-004, boundary report, package import tests |
| Separate declarative navgraph and LangGraph execution graph | 3, 8, 16 | compiler tests, raw-graph topology test, middleware/tool tests |
| Feature-composed rich nodes, bindings plane, and scalable package boundaries | 2-3, 9-10 | compiled contract, package tests, schema parity |
| Exact nine-node buyer flow, operations, transitions, and public/session-bound deep links | 3-4, 12-15, 17 | graph contract, route round trips, full-flow trace |
| Scoped context providers and one UI/agent operation boundary | 4-5, 8, 12-16 | redaction/context tests, runner conformance, agent tool trace |
| Developer-facing typed failures with no default handlers, phrase routing, or hidden fallback | 2, 5, 7-8, 10, 18 | failure projection tests, boundary/fallback scans |
| Durable authority, versioning, CAS, fencing, journals, claims, and replay | 4-7, 13, 17 | SQLite/conformance suites, restart and replay traces |
| Guest identity, canonical URL/history, SSE bootstrap/reconnect, retention, and cleanup | 4, 6-7, 9-10, 17 | cookie/deep-link tests, cursor-gap tests, browser restart proof |
| Encrypted private forms and exclusion from projection, SSE, model context, URLs, logs, and artifacts | 6-7, 10, 14, 17-18 | ciphertext/redaction tests, captured network and release scans |
| Guard/review lifecycle, no automatic write retry, and `external_outcome_unknown` handling | 5-8, 13, 15, 17 | crash-window tests, single-call proof, recovery trace |
| Real Medusa data path, exact `pp_system_default`, verified order re-read, and protected reset | 11-15, 17-18 | Store integration, order proof, before/after seed fingerprints |
| Framework, frontend, browser, real-model, coverage, clean-install, and proof-bundle gates | 16-18 | release verifier and complete sanitized artifact bundle |
| Local-only execution policy and exact smoke URLs | 11, 17-18 | environment record and smoke logs for ports 5198/8098/9100 |

Every approved design section maps to at least one implementation task and one executable or inspectable proof. A task may tighten a contract, but it may not weaken or silently reinterpret the approved design.

## Execution Order And Review Gates

- Execute Tasks 1-18 in order.
- Every task must have a fresh implementation worker, spec-compliance review, and code-quality review before its commit.
- A task is incomplete until its Medusa consumer test passes; framework-only green tests are intermediate evidence.
- Keep the dedicated Medusa stack down between live-integration tasks unless the next task immediately needs it.
- If the real model credential is unavailable, implementation may continue through deterministic test-only agent coverage, but the goal remains incomplete and the final release gate must report the blocker rather than substitute a model.
- If an ambiguous complete-cart outcome occurs during acceptance, stop placement, preserve evidence, reset only through the protected demo procedure, and rerun from a clean session. Never call complete-cart again for the ambiguous cart.

## Execution Handoff

The user explicitly requested Goal Mode and authorized implementation after this plan. Use the recommended **subagent-driven** execution mode: one fresh implementation agent per task, followed by spec and quality reviews. Inline execution is reserved for tightly coupled fixes that cannot be isolated without duplicating edits.
