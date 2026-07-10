# RouteDeck Full-Stack Framework Refactor Implementation Plan

> **Status: RETIRED on 2026-07-10. Do not execute this plan.** It was replaced
> by `../../../decisions/ADR-003-agentic-interaction-state-governor.md`. The plan
> expanded beyond proven Corpus behavior and changed RouteDeck's public dispatch
> contract before migrating Corpus, breaking the active product path. It is
> preserved only as historical design material.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor RouteDeck into one server-authoritative state and interaction kernel that powers a LangGraph-native Full Flow for ordinary developers and a Core Integration path for existing agents, with typed events/SSE, React state, comprehensive tests, a lightweight Corpus migration, and two standalone example projects.

**Architecture:** Build an executor-independent interaction kernel first, prove it by adapting an unchanged existing LangGraph agent, then implement the declarative Full Flow compiler as another executor construction path. Both modes use the same application specification, server-owned session state, version/idempotency rules, guard/review lifecycle, projection, surface, event, SSE, React-store, and conformance contracts. Corpus migrates last, after the framework is proven independently.

**Tech Stack:** Python 3.11+, Pydantic 2, LangGraph, FastAPI/Starlette SSE, React 18/19, TypeScript, `@routedeck/react`, pytest, Node test runner, Vite.

## Global Constraints

- LangGraph is the first-class Python execution substrate; custom compiled LangGraph graphs remain first-class.
- Full Flow and Core Integration must share one runtime kernel and one conformance suite.
- Framework-neutral RouteDeck contracts must not expose product literals or unnecessary LangGraph implementation types.
- Server session state is authoritative. Clients submit session identity, expected projection version, and idempotency key, never authoritative graph state.
- A dispatch is atomically claimed before executor invocation. Concurrent or repeated requests cannot both cross the side-effect boundary.
- RouteDeck does not claim exactly-once behavior across uncoordinated external systems. Executors receive the dispatch idempotency key; interrupted work is explicit and is never silently rerun.
- A function has one execution path. Compatibility behavior is an explicitly named adapter, never a hidden fallback.
- Missing executors, stores, event backends, models, inputs, surface registrations, or invariants fail loudly.
- Production application/example paths contain no fixtures, canned outputs, heuristic planners, silent synthetic data, or fake success.
- Test doubles and fixtures live only under test directories and are named as test-only objects.
- RouteDeck owns generic event sequencing and SSE framing; product code emits typed domain/execution events only.
- Event channels are `assistant`, `runtime`, `tool`, `surface`, and `diagnostic`; they share one envelope while retaining visibility isolation.
- An in-memory session/event backend is allowed only when explicitly configured for tests, examples, or development. It is never a production fallback.
- Before starting any backend/frontend service, ask the user to choose local, Mac mini LAN, or Mac mini Tailscale, then report exact commands and smoke URLs.
- Do not stage or commit implementation work without explicit git approval. Commit messages below are prepared checkpoints to use only after that approval.
- Preserve unrelated research/evaluation work in the shared worktree.

## Target File Map

### Shared Python kernel

- Create `routedeck_core/spec.py`: application, flow, surface, and declared-event specifications.
- Create `routedeck_core/execution.py`: executor narrow-waist protocols and execution result types.
- Create `routedeck_core/client_contract.py`: versioned, product-safe client contract exported from the application specification.
- Create `routedeck_core/session.py`: authoritative session store protocol, atomic dispatch claims, compare-and-set state, interruption records, and idempotent results.
- Create `routedeck_core/reviews.py`: explicit review records and lifecycle.
- Create `routedeck_core/events/__init__.py`: event public exports.
- Create `routedeck_core/events/models.py`: event envelope, channels, visibility, and typed payload base contracts.
- Create `routedeck_core/events/backend.py`: event backend/emitter/subscription protocols.
- Create `routedeck_core/events/memory.py`: explicitly selected development/test in-memory backend.
- Modify `routedeck_core/app.py`: declarative builder and compiled-app construction inputs.
- Modify `routedeck_core/runtime.py`: server-authoritative `RouteDeckInteractionRuntime`.
- Modify `routedeck_core/models.py`: versioned dispatch input and expanded operation/projection contracts.
- Create `routedeck_core/legacy.py`: explicitly selected temporary client-graph-state migration adapter.
- Modify `routedeck_core/__init__.py`: public exports.

### Durable reference backend

- Create `routedeck_sqlite/__init__.py`: public durable backend export.
- Create `routedeck_sqlite/backend.py`: transactional single-host session, dispatch-claim, event-log, replay, and outbox implementation.
- Create `routedeck_sqlite/schema.py`: explicit schema/version management.
- Modify `pyproject.toml`: package the backend and expose an explicit `sqlite`/`full` extra if dependencies require it.

### LangGraph execution

- Create `routedeck_langgraph/executor.py`: existing/custom compiled graph adapter.
- Create `routedeck_langgraph/compiler.py`: Full Flow application compiler.
- Create `routedeck_langgraph/flow.py`: declared outcome-to-public-node routing.
- Create `routedeck_langgraph/events.py`: LangGraph callback/event mapping.
- Modify `routedeck_langgraph/validation.py`: public interaction node/private execution node validation.
- Modify `routedeck_langgraph/__init__.py`: public exports.

### FastAPI/SSE transport

- Create `routedeck_fastapi/__init__.py`: public router factory exports.
- Create `routedeck_fastapi/router.py`: session, turn, dispatch, inspect, review, and event routes.
- Create `routedeck_fastapi/sse.py`: SSE encoding, heartbeats, replay cursor, disconnect cleanup, and channel filtering.
- Modify `pyproject.toml`: package `routedeck_fastapi` and add explicit `fastapi`/`full` extras.

### React runtime

- Create `react/src/RouteDeckEventClient.ts`: channel subscriptions, replay cursor, and reconnect behavior.
- Create `react/src/RouteDeckEventReducer.ts`: ordering, deduplication, stale projection rejection, and runtime-state reduction.
- Create `react/src/RouteDeckSurfaceRegistry.ts`: component-key registration and visible missing-component failures.
- Modify `react/src/RouteDeckStore.ts`: server-authoritative dispatch/session API and event reduction.
- Modify `react/src/types.ts`: event/session/version/idempotency types.
- Create `react/src/RouteDeckClientContract.ts`: contract loader and version validation.
- Modify `react/src/index.ts`: public exports.

### Standalone examples

- Create `examples/core-integration-document-review/`: unchanged existing LangGraph agent plus RouteDeck adapter, FastAPI app, React UI, tests, README, and compose file.
- Create `examples/full-flow-change-planner/`: declarative RouteDeck application compiled to LangGraph, FastAPI app, React UI, tests, README, and compose file.

### Corpus migration

- Modify `../saastoagent-v0.1/backend/corpus/graph/definitions.py`: one app specification for nodes, flows, operations, surfaces, and declared outcomes.
- Create `../saastoagent-v0.1/backend/corpus/graph/operations.py`: product context, guards, handlers, and agent planning.
- Modify `../saastoagent-v0.1/backend/corpus/graph/app.py`: thin RouteDeck composition only.
- Modify `../saastoagent-v0.1/backend/corpus/schemas/graph.py`: real product extensions only.
- Modify `../saastoagent-v0.1/backend/routes/corpus_graph.py`: RouteDeck-generated/product-prefixed transport.
- Modify `../saastoagent-v0.1/frontend/src/types/corpus.ts`: RouteDeck types directly.
- Modify `../saastoagent-v0.1/frontend/src/components/corpus/*.ts*`: RouteDeck event/store/surface contracts and component registry.
- Retire duplicate catalogs and compatibility paths only after call-site proof.

---

### Task 1: Lock the shared application specification

**Files:**
- Create: `routedeck_core/spec.py`
- Create: `routedeck_core/client_contract.py`
- Modify: `routedeck_core/models.py`
- Modify: `routedeck_core/__init__.py`
- Test: `tests/test_app_spec.py`
- Test: `tests/test_surface_spec.py`
- Test: `tests/test_client_contract.py`

**Interfaces:**
- Produces: `RouteDeckAppSpec`, `RouteDeckFlowSpec`, `RouteDeckSurfaceSpec`, `RouteDeckNodeSurfaceSpec`, `RouteDeckDeclaredEventSpec`, and versioned `RouteDeckClientContract`.
- Consumes: existing `RouteDeckManifest`, `RouteDeckSurfaceAffordance`, node/action/field models.

- [ ] **Step 1: Write failing tests for one-source flow and surface declarations**

```python
def test_branching_operation_requires_named_outcomes() -> None:
    spec = RouteDeckAppSpec(
        app_id="approval-app",
        state_type=ApprovalState,
        manifest=APPROVAL_MANIFEST,
        flows=[
            RouteDeckFlowSpec(from_node="review", operation_id="plan.decide", outcome="approved", to_node="approved"),
            RouteDeckFlowSpec(from_node="review", operation_id="plan.decide", outcome="rejected", to_node="rejected"),
        ],
        surfaces=APPROVAL_SURFACES,
    )

    assert spec.possible_target_nodes("review", "plan.decide") == ["approved", "rejected"]
    assert spec.single_target_node("review", "plan.decide") is None
```

```python
def test_surface_identity_and_node_placement_are_declared_once() -> None:
    surface = RouteDeckSurfaceSpec(
        surface_id="review.plan",
        component="PlanReviewSurface",
        role="active",
        variants=["default", "compact"],
        affordances=[],
    )
    placement = RouteDeckNodeSurfaceSpec(
        node_id="review",
        surface_id="review.plan",
        allowed_variants=["default", "compact"],
        default_variant="default",
    )

    assert placement.default_variant in surface.variants
```

- [ ] **Step 2: Run the focused tests and verify red failures**

Run: `python -m pytest tests/test_app_spec.py tests/test_surface_spec.py -q`

Expected: collection or import failure because the new specification types do not exist.

- [ ] **Step 3: Implement immutable specification types and compile-time validation**

```python
class RouteDeckFlowSpec(BaseModel):
    from_node: str
    operation_id: str
    outcome: str
    to_node: str


class RouteDeckSurfaceSpec(BaseModel):
    surface_id: str
    component: str
    role: Literal["frame", "active", "diagnostic"]
    slot: str | None = None
    variants: list[str] = Field(default_factory=lambda: ["default"])
    affordances: list[RouteDeckSurfaceAffordance] = Field(default_factory=list)


class RouteDeckNodeSurfaceSpec(BaseModel):
    node_id: str
    surface_id: str
    allowed_variants: list[str]
    default_variant: str
```

`RouteDeckAppSpec.validate_contract()` must reject unknown nodes/actions/surfaces, duplicate `(from_node, operation_id, outcome)` tuples, invalid default variants, and affordances targeting undeclared operations.

- [ ] **Step 4: Export one product-safe client contract from the specification**

Add a failing parity test proving the export contains the contract version,
public nodes, flow outcomes, operation/input metadata, surface identity and
placement, affordances, and public event schemas derived from the same
`RouteDeckAppSpec`. It must exclude handlers, prompts, private graph nodes,
credentials, raw state, and diagnostic-only fields. A frontend catalog with a
different node, flow, operation, or surface identity must fail parity checks.

- [ ] **Step 5: Remove single-target collapse from the new specification path**

`single_target_node()` returns a target only when exactly one declared outcome exists. `possible_target_nodes()` exposes all declared outcomes. Do not read an `ACTION_TARGETS` compatibility map.

- [ ] **Step 6: Run focused and existing manifest tests**

Run: `python -m pytest tests/test_app_spec.py tests/test_surface_spec.py tests/test_client_contract.py tests/test_core_contract.py tests/test_manifest_authoring.py -q`

Expected: all pass.

- [ ] **Step 7: Prepare the checkpoint commit after explicit git approval**

Suggested message: `feat(routedeck): add single-source application specification`

### Task 2: Add the executor narrow waist

**Files:**
- Create: `routedeck_core/execution.py`
- Create: `routedeck_core/events/__init__.py`
- Create: `routedeck_core/events/models.py`
- Create: `routedeck_core/events/backend.py`
- Modify: `routedeck_core/__init__.py`
- Test: `tests/test_execution_protocol.py`

**Interfaces:**
- Produces: `RouteDeckExecutor`, `RouteDeckExecutionContext`, `RouteDeckExecutionRequest`, `RouteDeckExecutionSnapshot`, `RouteDeckExecutionResult`, the base `RouteDeckEventPayload`/`RouteDeckEventDraft`, and the canonical `RouteDeckEventEmitter` protocol in `events/backend.py`.
- Consumes: `RouteDeckAppSpec`, product state models, typed event drafts.

- [ ] **Step 1: Write the protocol contract test**

```python
def test_executor_has_one_load_and_one_execute_path() -> None:
    assert {"load", "execute"}.issubset(RouteDeckExecutor.__dict__)
    assert "stream" not in RouteDeckExecutor.__dict__
```

```python
async def test_execute_receives_typed_emitter() -> None:
    executor = RecordingExecutor()
    await executor.execute(EXECUTION_REQUEST, emit=RecordingEmitter())
    assert executor.requests == [EXECUTION_REQUEST]
```

- [ ] **Step 2: Verify the tests fail before implementation**

Run: `python -m pytest tests/test_execution_protocol.py -q`

Expected: import failure for `RouteDeckExecutor`.

- [ ] **Step 3: Implement the protocol without a fallback stream method**

```python
@runtime_checkable
class RouteDeckExecutor(Protocol[StateT]):
    async def load(self, context: RouteDeckExecutionContext) -> RouteDeckExecutionSnapshot[StateT]: ...

    async def execute(
        self,
        request: RouteDeckExecutionRequest[StateT],
        *,
        emit: RouteDeckEventEmitter,
    ) -> RouteDeckExecutionResult[StateT]: ...
```

Execution events always flow through `emit`; do not add a second hidden `stream()` execution path.
`execution.py` imports the canonical emitter protocol from `events/backend.py`;
it must not define or re-export a second incompatible emitter interface.

- [ ] **Step 4: Test result validation**

Add cases proving a missing outcome for a branching operation and an undeclared public node both raise `RouteDeckValidationError`.

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_execution_protocol.py tests/test_app_spec.py -q`

Expected: all pass.

- [ ] **Step 6: Prepare the checkpoint commit after explicit git approval**

Suggested message: `feat(routedeck): define the shared executor protocol`

### Task 3: Make session state server-authoritative and idempotent

**Files:**
- Create: `routedeck_core/session.py`
- Create: `routedeck_core/legacy.py`
- Modify: `routedeck_core/models.py`
- Modify: `routedeck_core/runtime.py`
- Test: `tests/test_session_store.py`
- Test: `tests/test_runtime_concurrency.py`
- Test: `tests/test_runtime_idempotency.py`

**Interfaces:**
- Produces: `RouteDeckSessionStore`, `RouteDeckSessionRecord`, `RouteDeckDispatchClaim`, `RouteDeckDispatchStatus`, `RouteDeckInMemorySessionStore`, versioned/idempotent `RouteDeckDispatchInput`, and `RouteDeckInteractionRuntime.attach(...)`.
- Consumes: `RouteDeckExecutor`, `RouteDeckAppSpec`.

- [ ] **Step 1: Write stale-version and idempotency tests**

```python
async def test_stale_projection_is_rejected_before_executor() -> None:
    result = await runtime.dispatch(
        RouteDeckDispatchInput(
            session_id="session-1",
            operation_id="plan.approve",
            args={},
            expected_projection_version=3,
            idempotency_key="approve-1",
        )
    )
    assert result.accepted is False
    assert result.error_code == "stale_projection"
    assert executor.execute_count == 0
```

```python
async def test_duplicate_idempotency_key_executes_once() -> None:
    first = await runtime.dispatch(APPROVE_REQUEST)
    second = await runtime.dispatch(APPROVE_REQUEST)
    assert first == second
    assert executor.execute_count == 1
```

```python
async def test_concurrent_requests_cannot_both_cross_executor_boundary() -> None:
    first, second = await asyncio.gather(
        runtime.dispatch(request(idempotency_key="first", expected_projection_version=3)),
        runtime.dispatch(request(idempotency_key="second", expected_projection_version=3)),
    )
    assert sum(result.accepted for result in (first, second)) == 1
    assert executor.execute_count == 1
```

Add a crash-window test: after a claim has invoked the executor but before the
session result is committed, retrying the idempotency key returns an explicit
`dispatch_interrupted` result and does not invoke the executor again.

- [ ] **Step 2: Run tests and confirm failure**

Run: `python -m pytest tests/test_session_store.py tests/test_runtime_concurrency.py tests/test_runtime_idempotency.py -q`

Expected: new session/runtime interfaces are missing.

- [ ] **Step 3: Implement atomic dispatch claims and session storage**

```python
class RouteDeckSessionStore(Protocol):
    async def create(self, record: RouteDeckSessionRecord) -> None: ...
    async def load(self, app_id: str, session_id: str) -> RouteDeckSessionRecord: ...
    async def begin_dispatch(
        self,
        *,
        app_id: str,
        session_id: str,
        expected_projection_version: int,
        idempotency_key: str,
    ) -> RouteDeckDispatchClaim: ...
    async def complete_dispatch(
        self,
        claim: RouteDeckDispatchClaim,
        *,
        next_record: RouteDeckSessionRecord,
        result: RouteDeckDispatchResult,
    ) -> None: ...
    async def record_executor_result(
        self,
        claim: RouteDeckDispatchClaim,
        *,
        execution_result: RouteDeckExecutionResult,
    ) -> None: ...
    async def fail_dispatch(
        self,
        claim: RouteDeckDispatchClaim,
        *,
        failure: RouteDeckDispatchFailure,
    ) -> None: ...
```

`begin_dispatch()` atomically validates the current projection version, claims
the session/idempotency key, and returns one of `claimed`, `executor_completed`,
`completed`, `in_progress`, `interrupted`, or `stale`. A completed duplicate returns its
recorded result. An active or expired claim never triggers automatic executor
re-entry. After an executor returns, `record_executor_result()` durably advances
the claim before public state commit. `complete_dispatch()` atomically commits
the next authoritative state and idempotent result. `fail_dispatch()` records an
honest terminal failure without committing proposed product state.

`RouteDeckInMemorySessionStore` uses a per-session lock and is constructed
explicitly by tests/examples. Production stores must implement the same atomic
claim contract with a transaction or lease. `RouteDeckInteractionRuntime.attach()`
requires a store argument and never creates one implicitly.

- [ ] **Step 4: Replace client-authoritative dispatch fields**

```python
class RouteDeckDispatchInput(BaseModel):
    session_id: str
    operation_id: str | None = None
    surface_event: RouteDeckSurfaceInteractionEvent | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    expected_projection_version: int
    idempotency_key: str
    context: dict[str, Any] = Field(default_factory=dict)
```

`graph_state` is accepted only by `RouteDeckLegacyClientStateAdapter`, which must be selected explicitly during Corpus migration.

- [ ] **Step 5: Prove guards/review precede the executor and the claim encloses side effects**

Add tests for blocked guard, review staging without execution, approval claiming
exactly once, two concurrent keys at one projection version, duplicate in-flight
keys, executor-result persistence failure, expired/interrupted claims,
undeclared returned nodes, state unchanged on failure, and propagation of the
idempotency key into executor context. Never
describe external side effects as exactly-once unless the downstream system
participates in the same transaction; handlers must use the supplied key when
the downstream API supports idempotency.

- [ ] **Step 6: Run runtime regression tests**

Run: `python -m pytest tests/test_session_store.py tests/test_runtime_concurrency.py tests/test_runtime_idempotency.py tests/test_runtime_store_contract.py tests/test_runtime_ownership.py -q`

Expected: all pass after explicitly adapting legacy test setup.

- [ ] **Step 7: Prepare the checkpoint commit after explicit git approval**

Suggested message: `feat(routedeck): make runtime state server authoritative`

### Task 4: Implement explicit review lifecycle

**Files:**
- Create: `routedeck_core/reviews.py`
- Modify: `routedeck_core/runtime.py`
- Test: `tests/test_review_lifecycle.py`

**Interfaces:**
- Produces: `RouteDeckReviewRecord`, `RouteDeckReviewStatus`, `stage_review`, `approve_review`, `reject_review`.
- Consumes: session store, operation policy, executor.

- [ ] **Step 1: Write review lifecycle tests**

Cover staged, approved, rejected, expired, duplicate approval, mismatched operation, and executor-failure cases.

```python
async def test_review_approval_executes_exactly_once() -> None:
    staged = await runtime.dispatch(WRITE_REQUEST)
    approved = await runtime.approve_review(staged.review.review_id, APPROVE_INPUT)
    repeated = await runtime.approve_review(staged.review.review_id, APPROVE_INPUT)
    assert approved.accepted is True
    assert repeated.error_code == "review_already_resolved"
    assert executor.execute_count == 1
```

- [ ] **Step 2: Run the review suite red**

Run: `python -m pytest tests/test_review_lifecycle.py -q`

Expected: missing review APIs.

- [ ] **Step 3: Implement explicit persisted review records**

Review state belongs in the authoritative session record. Staging emits a
review-required event and never calls the executor. Approval/rejection use the
same atomic claim/version boundary as automatic dispatch so concurrent approval
requests cannot both invoke the executor.

- [ ] **Step 4: Run review and runtime suites**

Run: `python -m pytest tests/test_review_lifecycle.py tests/test_runtime_concurrency.py tests/test_runtime_idempotency.py -q`

Expected: all pass.

- [ ] **Step 5: Prepare the checkpoint commit after explicit git approval**

Suggested message: `feat(routedeck): add persisted review lifecycle`

### Task 5: Build the typed event kernel

**Files:**
- Modify: `routedeck_core/events/__init__.py`
- Modify: `routedeck_core/events/models.py`
- Modify: `routedeck_core/events/backend.py`
- Create: `routedeck_core/events/memory.py`
- Modify: `routedeck_core/runtime.py`
- Modify: `routedeck_core/models.py`
- Modify: `routedeck_core/__init__.py`
- Create: `routedeck_sqlite/__init__.py`
- Create: `routedeck_sqlite/backend.py`
- Create: `routedeck_sqlite/schema.py`
- Modify: `pyproject.toml`
- Test: `tests/events/test_event_models.py`
- Test: `tests/events/test_event_backend.py`
- Test: `tests/events/test_event_ordering.py`
- Test: `tests/events/test_event_replay.py`
- Test: `tests/events/test_event_visibility.py`
- Test: `tests/sqlite/test_sqlite_session_backend.py`
- Test: `tests/sqlite/test_sqlite_event_backend.py`
- Test: `tests/sqlite/test_sqlite_outbox.py`
- Test: `tests/sqlite/test_sqlite_reopen.py`

**Interfaces:**
- Produces: expanded `RouteDeckEvent`, `RouteDeckEventBackend`, completed `RouteDeckEventEmitter` semantics, `RouteDeckEventSubscription`, coordinated `RouteDeckRuntimeBackend`, and explicit `RouteDeckInMemoryBackend`.
- Consumes: app/session/run/turn/operation identity and projection versions from the interaction runtime.

- [ ] **Step 1: Write event-envelope and channel tests**

```python
def test_event_envelope_has_stable_correlation_and_sequence() -> None:
    event = RouteDeckEvent(
        schema_version="1",
        event_id="evt-1",
        event_type="projection_update",
        channel="runtime",
        visibility="product",
        app_id="approval-app",
        session_id="session-1",
        sequence=7,
        occurred_at=datetime.now(timezone.utc),
        run_id="run-1",
        turn_id="turn-1",
        operation_id="plan.approve",
        graph_node="approved",
        projection_version=3,
        payload=ProjectionUpdatePayload(projection=projection(version=3)),
    )
    assert event.sequence == 7
```

Add failures for diagnostic payload on public visibility, assistant deltas on runtime channel, missing projection payload, and non-monotonic sequence.

- [ ] **Step 2: Run event tests red**

Run: `python -m pytest tests/events -q`

Expected: event package missing.

- [ ] **Step 3: Implement the envelope and standard event registry**

```python
PayloadT = TypeVar("PayloadT", bound=RouteDeckEventPayload)


class RouteDeckEvent(BaseModel, Generic[PayloadT]):
    schema_version: Literal["1"] = "1"
    event_id: str
    event_type: str
    channel: Literal["assistant", "runtime", "tool", "surface", "diagnostic"]
    visibility: Literal["public", "product", "diagnostic"]
    app_id: str
    session_id: str
    sequence: int = Field(ge=1)
    occurred_at: datetime
    run_id: str | None = None
    turn_id: str | None = None
    operation_id: str | None = None
    graph_node: str | None = None
    projection_version: int | None = None
    payload: PayloadT
```

`PayloadT` is bound to `RouteDeckEventPayload`. Standard event types use concrete
framework payload models such as `ProjectionUpdatePayload`,
`OperationCompletedPayload`, `MessageDeltaPayload`, and `ToolFailedPayload`.
Declared product event types register a concrete payload model in
`RouteDeckAppSpec`. Undeclared event types, arbitrary payload dictionaries,
event/payload mismatches, and channel/visibility mismatches fail before
persistence.

Move the current public `RouteDeckEvent` definition out of
`routedeck_core/models.py`, update internal imports, and re-export the one
canonical event type from `routedeck_core.__init__` during the compatibility
window. There must not be two independently defined event envelopes.

- [ ] **Step 4: Implement backend semantics**

The backend allocates one session-global sequence across all channels, persists
before fan-out, replays strictly after an event ID, filters by channel/visibility,
uses bounded subscriber queues, reports overflow explicitly, and cleans
subscriptions on disconnect. Filtered subscriptions preserve relative global
order but may contain sequence gaps for excluded channels. A multiplexed
subscription is the canonical source for one stateful client reducer; independent
channel subscriptions keep independent cursors and are never merged by comparing
one shared last-sequence value.

- [ ] **Step 5: Implement a durable transactional SQLite reference backend**

Create `RouteDeckSqliteBackend` implementing the coordinated session/event
backend for single-host deployments and both standalone examples. Use explicit
schema versioning, transactions, unique constraints for dispatch idempotency and
session sequence, durable replay indexes, and an outbox. Successful dispatch
commit must atomically persist the next session/projection, idempotent result,
`projection_update`, and terminal event before fan-out. Provisional streaming
events may persist earlier under the claimed run; if work is interrupted they
remain non-success evidence and recovery appends an explicit interrupted
terminal event. Reopening the database in a new process must preserve sessions,
claims, results, events, and replay cursors.

Add `tests/sqlite/test_sqlite_session_backend.py`,
`tests/sqlite/test_sqlite_event_backend.py`,
`tests/sqlite/test_sqlite_outbox.py`, and
`tests/sqlite/test_sqlite_reopen.py`. The in-memory backend remains explicitly
test/development-only and is never an implicit fallback.

- [ ] **Step 6: Wire runtime lifecycle events in stable order**

Required order for an accepted automatic operation:

```text
operation_started
executor-emitted tool/assistant events
graph_transition (when public node changes)
projection_update
operation_completed
```

Rejected/failed operations end with `operation_rejected` or a typed error event and never emit a success terminal event.

- [ ] **Step 7: Run event, SQLite, and runtime suites**

Run: `python -m pytest tests/events tests/sqlite tests/test_runtime_idempotency.py tests/test_review_lifecycle.py -q`

Expected: all pass.

- [ ] **Step 8: Prepare the checkpoint commit after explicit git approval**

Suggested message: `feat(routedeck): add typed ordered event kernel`

### Task 6: Add FastAPI and SSE transport

**Files:**
- Create: `routedeck_fastapi/__init__.py`
- Create: `routedeck_fastapi/router.py`
- Create: `routedeck_fastapi/sse.py`
- Modify: `pyproject.toml`
- Test: `tests/test_fastapi_transport.py`
- Test: `tests/events/test_sse_encoding.py`
- Test: `tests/events/test_fastapi_channels.py`

**Interfaces:**
- Produces: `create_routedeck_router(runtime, prefix, auth_dependencies)` and `encode_route_deck_sse(event)`.
- Consumes: interaction runtime, coordinated backend, exported client contract, and caller-supplied auth dependencies.

- [ ] **Step 1: Write HTTP/SSE contract tests**

Required routes under a caller-selected prefix:

```text
GET  /contract
POST /sessions
GET  /sessions/{session_id}/snapshot
POST /sessions/{session_id}/turns
POST /sessions/{session_id}/dispatch
POST /sessions/{session_id}/inspect
POST /sessions/{session_id}/reviews/{review_id}/approve
POST /sessions/{session_id}/reviews/{review_id}/reject
GET  /sessions/{session_id}/events/{channel}
GET  /sessions/{session_id}/events?channels=assistant,runtime,surface
```

Tests assert `/contract` returns the exact versioned export derived from the
runtime application specification; SSE frames contain `id`, `event`, and JSON
`data`; `Last-Event-ID` replays strictly after the cursor; channel authorization
prevents diagnostic leakage.

- [ ] **Step 2: Run transport tests red**

Run: `python -m pytest tests/test_fastapi_transport.py tests/events/test_sse_encoding.py tests/events/test_fastapi_channels.py -q`

Expected: `routedeck_fastapi` is missing.

- [ ] **Step 3: Implement exact SSE encoding**

```python
def encode_route_deck_sse(event: RouteDeckEvent) -> bytes:
    data = event.model_dump_json()
    return f"id: {event.event_id}\nevent: {event.event_type}\ndata: {data}\n\n".encode("utf-8")
```

Keepalive uses `: ping\n\n`; it is not persisted as a semantic event. Network close without a terminal semantic event remains interrupted.

- [ ] **Step 4: Implement router factory with supplied auth dependencies**

Product auth remains caller-owned. Diagnostic channel mounting requires an explicit diagnostic dependency. Do not infer authentication or silently expose it.

- [ ] **Step 5: Test overflow, disconnect cleanup, replay, and terminal error behavior**

Run: `python -m pytest tests/test_fastapi_transport.py tests/events -q`

Expected: all pass.

- [ ] **Step 6: Prepare the checkpoint commit after explicit git approval**

Suggested message: `feat(routedeck): add FastAPI session and SSE transport`

### Task 7: Implement Core Integration for existing LangGraph agents

**Files:**
- Create: `routedeck_langgraph/executor.py`
- Create: `routedeck_langgraph/events.py`
- Create: `routedeck_langgraph/flow.py`
- Modify: `routedeck_langgraph/validation.py`
- Modify: `routedeck_langgraph/__init__.py`
- Test: `tests/langgraph/test_existing_graph_executor.py`
- Test: `tests/langgraph/test_private_nodes.py`
- Test: `tests/langgraph/test_existing_graph_events.py`

**Interfaces:**
- Produces: `ExistingLangGraphExecutor` implementing `RouteDeckExecutor`.
- Consumes: compiled LangGraph graph, input/result/public-node mapping callables, application spec, emitter.

- [ ] **Step 1: Write an unchanged-private-graph test**

```python
executor = ExistingLangGraphExecutor(
    graph=compiled_graph,
    input_mapper=to_graph_input,
    result_mapper=from_graph_result,
    public_node_resolver=resolve_public_node,
)
runtime = RouteDeckInteractionRuntime.attach(
    spec=DOCUMENT_REVIEW_SPEC,
    executor=executor,
    backend=runtime_backend,
)
```

Assert private nodes such as `extract_requirements`, `assess_risks`, and `synthesize_analysis` never appear as RouteDeck navgraph nodes.

- [ ] **Step 2: Run LangGraph adapter tests red**

Run: `python -m pytest tests/langgraph/test_existing_graph_executor.py tests/langgraph/test_private_nodes.py tests/langgraph/test_existing_graph_events.py -q`

Expected: existing executor adapter missing.

- [ ] **Step 3: Implement mapping without public/private node equality**

The adapter invokes the existing compiled graph, maps its result to `RouteDeckExecutionResult`, resolves one declared public node/outcome, and maps LangGraph callbacks to typed tool/assistant events through the supplied emitter.

- [ ] **Step 4: Prove existing graph checkpoint/resume behavior remains intact**

Use the existing graph's own checkpointer for private executor state only.
RouteDeck's coordinated backend remains authoritative for public interaction
state, operation legality, projection version, and terminal result. The adapter
maps immutable RouteDeck execution input into the private graph and maps its
checkpoint/result back; private nodes and checkpoint revisions never become
public session authority.

Test the split failure boundary explicitly: the existing graph checkpoints a
completed private run, then the RouteDeck public commit/outbox is forced to
fail. The public projection must remain unchanged, no success terminal event may
appear, the claim becomes `executor_completed` or `interrupted`, and retry must
not execute the graph again. Recovery is an explicit reconciler that inspects
the recorded run/checkpoint and commits or rejects it; there is no hidden rerun
fallback.

- [ ] **Step 5: Run LangGraph and shared runtime suites**

Run: `python -m pytest tests/langgraph tests/test_execution_protocol.py tests/test_runtime_concurrency.py tests/events -q`

Expected: all pass.

- [ ] **Step 6: Prepare the checkpoint commit after explicit git approval**

Suggested message: `feat(routedeck): adapt existing LangGraph agents`

### Task 8: Build the standalone Core Integration document-review project

**Files:**
- Create: `examples/core-integration-document-review/README.md`
- Create: `examples/core-integration-document-review/.env.example`
- Create: `examples/core-integration-document-review/compose.yaml`
- Create: `examples/core-integration-document-review/backend/pyproject.toml`
- Create: `examples/core-integration-document-review/backend/src/document_review/existing_agent/{state.py,graph.py,model.py}`
- Create: `examples/core-integration-document-review/backend/src/document_review/routedeck_integration/{definition.py,adapter.py}`
- Create: `examples/core-integration-document-review/backend/src/document_review/server.py`
- Create: `examples/core-integration-document-review/backend/tests/{fakes.py,test_existing_agent_standalone.py,test_adapter_contract.py,test_core_flow.py,test_events.py,test_fail_loud.py}`
- Create: `examples/core-integration-document-review/frontend/` Vite/React app and `src/surfaces/*.tsx`

**Interfaces:**
- Produces: a self-contained existing-agent adoption proof.
- Consumes: installed RouteDeck packages, durable SQLite backend, exported client contract, and `@routedeck/react`.

- [ ] **Step 1: Write failing independence and anti-fallback tests**

```python
def test_existing_agent_package_has_no_routedeck_imports() -> None:
    source = "\n".join(path.read_text() for path in EXISTING_AGENT_ROOT.rglob("*.py"))
    assert "routedeck" not in source.lower()
```

```python
def test_live_model_dependency_fails_loudly(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(DocumentReviewConfigurationError, match="OPENAI_API_KEY"):
        build_live_document_review_model()
```

- [ ] **Step 2: Implement the independent graph**

Real flow uses user-pasted document text:

```text
ingest -> extract_requirements -> assess_risks -> synthesize_analysis
```

No document or analysis is bundled in the live path. A test-only `FakeDocumentReviewModel` lives in `backend/tests/fakes.py`.

- [ ] **Step 3: Implement RouteDeck interaction mapping**

Public nodes are `input`, `analyzing`, `review`, and `accepted`. Operations are `document.submit`, `analysis.rerun`, `analysis.accept`, and `session.reset`. The adapter maps the existing graph result into these public outcomes without modifying `existing_agent/`.

- [ ] **Step 4: Implement the React app using `@routedeck/react`**

The frontend defines only product surface components and a component registry. It must not duplicate node/edge/operation truth or encode SSE manually.

- [ ] **Step 5: Run backend/frontend tests**

Run from backend: `python -m pytest -q`

Run from frontend, stopping on any non-zero exit:

```powershell
npm ci
npm test
npm run build
```

Expected: all pass without a live model because tests inject the named test double; live agent execution without a credential fails explicitly.

- [ ] **Step 6: Run service/browser smoke after runtime location is selected**

Suggested local URLs if the user selects local: frontend `http://127.0.0.1:5192`, backend health `http://127.0.0.1:8092/api/health`.

- [ ] **Step 7: Prepare the checkpoint commit after explicit git approval**

Suggested message: `feat(examples): add existing-agent RouteDeck integration`

### Task 9: Implement the Full Flow LangGraph compiler

**Files:**
- Create: `routedeck_langgraph/compiler.py`
- Create: `routedeck_langgraph/compiled_app.py`
- Modify: `routedeck_core/app.py`
- Modify: `routedeck_langgraph/__init__.py`
- Test: `tests/langgraph/test_full_flow_compiler.py`
- Test: `tests/langgraph/test_operation_routing.py`
- Test: `tests/langgraph/test_compile_validation.py`
- Test: `tests/langgraph/test_checkpoint_resume.py`
- Test: `tests/langgraph/test_execution_events.py`

**Interfaces:**
- Produces: fluent `RouteDeckApp` Full Flow API and `RouteDeckCompiledApp` containing spec, compiled domain executor, interaction runtime, router factory, and exported client contract.
- Consumes: app spec, handlers, context provider, guard policy, and coordinated runtime backend.

- [ ] **Step 1: Write the target builder test**

```python
compiled = (
    RouteDeckApp("change-planner")
    .state(ChangePlannerState)
    .nodes(CHANGE_NODES)
    .operations(CHANGE_OPERATIONS)
    .flows(CHANGE_FLOWS)
    .surfaces(CHANGE_SURFACES)
    .context(ChangePlannerContextProvider())
    .guards(ChangePlannerGuardPolicy())
    .handlers(CHANGE_HANDLERS)
    .backend(RouteDeckSqliteBackend("change-planner.db"))
    .compile()
)

assert isinstance(compiled.runtime, RouteDeckInteractionRuntime)
assert compiled.spec.app_id == "change-planner"
```

- [ ] **Step 2: Write compile-time failure cases**

Reject missing handlers, undeclared handlers, duplicate outcomes, branching without outcomes, unknown surfaces/components, invalid variants, affordances targeting unknown operations, unsafe automatic operations without explicit policy, and absent session/event backends.

- [ ] **Step 3: Run compiler tests red**

Run: `python -m pytest tests/langgraph/test_full_flow_compiler.py tests/langgraph/test_compile_validation.py -q`

Expected: builder methods/compiler missing.

- [ ] **Step 4: Compile domain execution without creating a second kernel**

```text
RouteDeckInteractionRuntime
  -> load/validate/guard/review/claim in the shared kernel
  -> FullFlowLangGraphExecutor
       -> select declared product handler
       -> invoke product behavior
       -> normalize declared outcome and state delta
  -> validate outcome/commit/project/emit in the shared kernel
```

The compiled LangGraph executor owns only domain-handler invocation and declared
outcome normalization. It must not reimplement session loading, operation
legality, guard evaluation, review staging, dispatch claims, state commit,
projection, or terminal event ordering. Those stay in
`RouteDeckInteractionRuntime` for both adoption modes. Product source supplies
declarations and handlers, not LangGraph construction or a
`RouteDeckRuntimeBase` subclass.

- [ ] **Step 5: Prove checkpoint/resume and event parity with Core Integration**

Run: `python -m pytest tests/langgraph -q`

Expected: all pass.

- [ ] **Step 6: Prepare the checkpoint commit after explicit git approval**

Suggested message: `feat(routedeck): compile full-flow apps over LangGraph`

### Task 10: Upgrade the React event and surface runtime

**Files:**
- Create: `react/src/RouteDeckEventClient.ts`
- Create: `react/src/RouteDeckEventReducer.ts`
- Create: `react/src/RouteDeckSurfaceRegistry.ts`
- Create: `react/src/RouteDeckClientContract.ts`
- Modify: `react/src/RouteDeckStore.ts`
- Modify: `react/src/types.ts`
- Modify: `react/src/index.ts`
- Test: `react/tests/event-client.test.mjs`
- Test: `react/tests/event-reducer.test.mjs`
- Test: `react/tests/event-ordering.test.mjs`
- Test: `react/tests/channel-visibility.test.mjs`
- Test: `react/tests/surface-registry.test.mjs`

**Interfaces:**
- Produces: event client/reducer, server-authoritative store, product surface registry.
- Consumes: FastAPI session/event endpoints and exported RouteDeck application contract.

- [ ] **Step 1: Write red tests for ordering, dedupe, and visibility**

```ts
test('deduplicates ids and requests resync for a late unseen event', () => {
  const state1 = reduceRouteDeckEvent(initialState, event({ event_id: 'e2', sequence: 2 }))
  const duplicate = reduceRouteDeckEvent(state1, event({ event_id: 'e2', sequence: 2 }))
  const gapIsValid = reduceRouteDeckEvent(duplicate, event({ event_id: 'e4', sequence: 4 }))
  const late = reduceRouteDeckEvent(gapIsValid, event({ event_id: 'e3', sequence: 3 }))
  assert.equal(duplicate.lastSequence, 2)
  assert.equal(gapIsValid.lastSequence, 4)
  assert.equal(late.connectionStatus, 'resync_required')
})
```

```ts
test('rejects stale projection updates', () => {
  const next = reduceRouteDeckEvent(stateAtVersion(4), projectionEvent(3))
  assert.equal(next.projection.projection_version, 4)
})
```

- [ ] **Step 2: Make remote/server-authoritative navigation the default**

Local navigation remains available only as an explicitly named presentation-only mode and cannot mutate authoritative graph state.

- [ ] **Step 3: Implement multiplexed store subscription and scoped replay cursors**

`RouteDeckStore` opens one multiplexed subscription for its selected authorized
channel set, so one reducer receives those events in persisted order. It stores
the last event ID/sequence per `(session_id, channel_set)` subscription and
reconnects with `Last-Event-ID`. Sequence gaps are valid when excluded channels
own intervening events. A lower unseen sequence on the same subscription is a
protocol violation that triggers snapshot/replay resynchronization, not a blind
drop. Independent assistant/tool/diagnostic viewers keep independent cursors and
must not feed one reducer through a shared global last-sequence check.

- [ ] **Step 4: Implement visible missing-component failure**

`RouteDeckSurfaceRegistry.resolve(component)` throws `RouteDeckSurfaceComponentMissingError` with the missing component key. It does not silently render an empty surface.

- [ ] **Step 5: Run React suites**

Run: `cd react; npm test`

Expected: existing and new tests pass.

- [ ] **Step 6: Prepare the checkpoint commit after explicit git approval**

Suggested message: `feat(react): consume ordered RouteDeck event streams`

### Task 11: Build the standalone Full Flow change-planner project

**Files:**
- Create: `examples/full-flow-change-planner/README.md`
- Create: `examples/full-flow-change-planner/.env.example`
- Create: `examples/full-flow-change-planner/compose.yaml`
- Create: `examples/full-flow-change-planner/backend/pyproject.toml`
- Create: `examples/full-flow-change-planner/backend/src/change_planner/{definition.py,behavior.py,server.py}`
- Create: `examples/full-flow-change-planner/backend/tests/{fakes.py,test_definition.py,test_full_flow.py,test_http_contract.py,test_events.py,test_fail_loud.py}`
- Create: `examples/full-flow-change-planner/frontend/` Vite/React app and `src/surfaces/*.tsx`

**Interfaces:**
- Produces: a self-contained Full Flow adoption proof.
- Consumes: public RouteDeck builder/compiler, durable SQLite backend, FastAPI adapter, exported client contract, and React package.

- [ ] **Step 1: Write the anti-plumbing boundary test**

```python
def test_full_flow_product_has_no_framework_plumbing() -> None:
    source = "\n".join(path.read_text() for path in PRODUCT_SOURCE.rglob("*.py"))
    for forbidden in ["import langgraph", "RouteDeckRuntimeBase", "StreamingResponse", "data:", "_sse"]:
        assert forbidden not in source
```

- [ ] **Step 2: Define one real product interaction contract**

User-provided change brief flow:

```text
brief --brief.submit--> planning --plan.ready--> review
review --plan.request_revision/revision_requested--> planning
review --plan.approve/approved--> approved
```

The real model produces a structured change plan. Missing brief, missing model credential, model failure, invalid structured output, guard failure, stale projection, and duplicate dispatch all fail explicitly.

- [ ] **Step 3: Implement product declarations and behavior only**

Production source imports RouteDeck but not LangGraph, projection builders, event backends, or SSE formatters. `FakePlannerModel` lives only in `backend/tests/fakes.py`.

- [ ] **Step 4: Implement React surfaces**

Components: `ChangeBriefSurface`, `PlanningSurface`, `PlanReviewSurface`, and `ApprovedPlanSurface`. The frontend registers component keys and consumes RouteDeck contracts without repeating nodes/edges/operations.

- [ ] **Step 5: Run tests/build**

Run from backend: `python -m pytest -q`

Run from frontend, stopping on any non-zero exit:

```powershell
npm ci
npm test
npm run build
```

Expected: all pass.

- [ ] **Step 6: Run service/browser smoke after runtime location is selected**

Suggested local URLs if selected: frontend `http://127.0.0.1:5191`, backend health `http://127.0.0.1:8091/api/health`.

- [ ] **Step 7: Prepare the checkpoint commit after explicit git approval**

Suggested message: `feat(examples): add RouteDeck full-flow change planner`

### Task 12: Add shared two-mode conformance testing

**Files:**
- Create: `routedeck_testing/__init__.py`
- Create: `routedeck_testing/conformance.py`
- Create: `tests/conformance/test_runtime_matrix.py`
- Modify: both standalone example test configurations.
- Modify: `pyproject.toml` package/test extras.

**Interfaces:**
- Produces: `RouteDeckConformanceHarness` and a runtime-mode/backend matrix.
- Consumes: any `RouteDeckInteractionRuntime` plus memory and SQLite coordinated backend factories.

- [ ] **Step 1: Write one matrix over both executors**

```python
@pytest.mark.parametrize("runtime_factory", [full_flow_runtime, core_integration_runtime])
@pytest.mark.parametrize("backend_factory", [memory_backend, sqlite_backend])
async def test_runtime_modes_share_interaction_semantics(runtime_factory, backend_factory) -> None:
    runtime = runtime_factory(backend=backend_factory())
    await assert_illegal_operation_rejected(runtime)
    await assert_missing_fields_rejected(runtime)
    await assert_guard_blocks_before_execution(runtime)
    await assert_review_executes_once(runtime)
    await assert_stale_version_rejected(runtime)
    await assert_ordered_visible_events(runtime)
    await assert_surface_resolution(runtime)
    await assert_replay_is_idempotent(runtime)
    await assert_client_contract_matches_spec(runtime)
    await assert_state_result_and_terminal_event_commit_atomically(runtime)
```

The durable-backend lane also closes/reopens storage and reruns snapshot,
idempotent-result, and replay assertions. Backend-specific tests may cover
single-host limitations, but adoption modes may not change kernel semantics.

- [ ] **Step 2: Add anti-drift scans**

Assert no Corpus/SaaStoAgent/Medusa imports in either example, no LangGraph import in Full Flow product source, no RouteDeck import in Core Integration `existing_agent/`, no manual SSE encoder/event bus, and no production fake model or deterministic output table.

- [ ] **Step 3: Run the conformance suite**

Run: `python -m pytest tests/conformance -q`

Expected: both modes pass identical assertions.

- [ ] **Step 4: Prepare the checkpoint commit after explicit git approval**

Suggested message: `test(routedeck): enforce two-mode conformance`

### Task 13: Remove remaining Corpus identity aliases

**Files:**
- Modify: `../saastoagent-v0.1/backend/corpus/schemas/graph.py`
- Modify: `../saastoagent-v0.1/backend/corpus/schemas/__init__.py`
- Modify: `../saastoagent-v0.1/frontend/src/types/corpus.ts`
- Modify: `../saastoagent-v0.1/frontend/src/types/entry.ts`
- Modify: Corpus backend/frontend boundary tests.

**Interfaces:**
- Produces: direct RouteDeck surface/navigation/action/manifest/runtime types plus genuine Corpus extensions only.
- Consumes: RouteDeck Python/React contracts.

- [ ] **Step 1: Write failing negative-boundary tests**

Assert no pass-through `CorpusSurface` or `CorpusGraphNavigationLocation`, no active Corpus import of `EntryActionCard`, `EntryGraphManifest`, `EntryTurnMessage`, or `EntryUIArtifact`, and no tests that require those wrappers.

- [ ] **Step 2: Replace wrappers and aliases**

Use `RouteDeckSurface` and `RouteDeckGraphNavigationLocation` directly. Retain `CorpusGraphState` and `CorpusContextLens` because they add product fields. Remove unused `CorpusGraphResponse`/`CorpusGraphTurnResponse` after confirming no active call sites.

- [ ] **Step 3: Run backend/frontend type tests**

Run: `python -m pytest backend/tests/test_routedeck_schema_boundary.py backend/tests/test_corpus_surface_structure.py -q`

Run: `cd frontend; npm run type-check`

Expected: pass.

- [ ] **Step 4: Prepare the checkpoint commit after explicit git approval**

Suggested message: `refactor(corpus): remove remaining framework aliases`

### Task 14: Migrate Corpus to RouteDeck Full Flow vertically

**Files:**
- Modify: `../saastoagent-v0.1/backend/corpus/graph/definitions.py`
- Create: `../saastoagent-v0.1/backend/corpus/graph/operations.py`
- Modify: `../saastoagent-v0.1/backend/corpus/graph/app.py`
- Modify: `../saastoagent-v0.1/backend/routes/corpus_graph.py`
- Modify: Corpus runtime, planning, action, guard, review, SSE, and browser tests.

**Interfaces:**
- Produces: thin Corpus definition/composition with product domain behavior only.
- Consumes: RouteDeck Full Flow builder/compiler, product-prefixed FastAPI router, shared events/React store.

- [ ] **Step 1: Add the final structural boundary test**

The active Corpus backend must have no `RouteDeckRuntimeBase` subclass, generic surface registry, manual projection builder, `_sse`, event dictionary construction, `ACTION_TARGETS`, client graph-state round trip, or generic diagnostics assembly.

- [ ] **Step 2: Convert declarations to one app specification**

Move nodes, flows/outcomes, operations, surface identities/variants/affordances, and declared event types into `definitions.py`. Surface dynamic props remain product provider behavior; they do not redefine surface identity.

- [ ] **Step 3: Extract product behavior into `operations.py`**

Keep DB queries, auth/tenancy facts, product guards, domain handlers, Corpus planning prompts, model calls, and dynamic surface props. Return typed outcomes/results/events through RouteDeck protocols.

- [ ] **Step 4: Migrate one low-risk real operation end to end**

Start with `saas_agent.open`: product declaration -> RouteDeck validation -> Corpus handler -> LangGraph execution -> ordered RouteDeck events -> projection -> React store. Run its focused tests before migrating other operation groups.

- [ ] **Step 5: Migrate remaining operation groups**

Order: navigation/auth, agent selection/setup, connection/catalog, content/knowledge/memory, execution/review, learning/QA, then Corpus assistant turns.

- [ ] **Step 6: Move Corpus assistant emissions into the shared event emitter**

Corpus owns prompts/text meaning; RouteDeck owns event envelope, sequence, visibility, channel, SSE framing, and replay. Preserve public redaction and fail loudly when model configuration is absent.

- [ ] **Step 7: Mount RouteDeck transport under product-owned Corpus routes**

Keep `/api/corpus/*` ownership and caller auth dependencies. Remove route-local SSE formatting and state reconstruction.

- [ ] **Step 8: Run focused and full Corpus suites**

Run:

```powershell
python -m pytest backend/tests/test_app_graph_contract.py backend/tests/test_corpus_graph_contract.py backend/tests/test_corpus_routedeck_runtime.py backend/tests/test_corpus_routedeck_state.py backend/tests/test_corpus_turn_planning.py backend/tests/test_corpus_runtime_structure.py backend/tests/test_routedeck_schema_boundary.py -q
```

Then run the full backend suite, frontend type check/build, and browser suites in the user-selected runtime location.

- [ ] **Step 9: Prepare the checkpoint commit after explicit git approval**

Suggested message: `refactor(corpus): run on RouteDeck full flow`

### Task 15: Retire duplicate truths and compatibility paths

**Files:**
- Modify/delete after call-site proof: `../saastoagent-v0.1/backend/services/route_deck/**`
- Modify/delete after call-site proof: `../saastoagent-v0.1/backend/services/saas_agent_route_deck.py`
- Modify: frontend Corpus catalogs and legacy Entry utilities.
- Modify: architecture maps, component docs, tests.

**Interfaces:**
- Produces: one canonical Corpus application specification and explicit surviving compatibility boundary, if any.
- Consumes: call-site inventory and executable tests.

- [ ] **Step 1: Inventory active call sites and classify each path**

Classifications are `canonical`, `explicit compatibility`, or `unreferenced`. Record endpoints/tests/consumers before deleting anything.

- [ ] **Step 2: Delete unreferenced catalogs and derive deterministic targets from flows**

Remove `ACTION_TARGETS`; use flow outcomes. Remove frontend node/operation/surface truth that can be read from the application contract. Frontend keeps only product component registration and product copy.

- [ ] **Step 3: Make any surviving compatibility adapter explicit**

Name it `Legacy...Adapter`, mount it only where required, emit a visible deprecation marker, and test that the canonical path never invokes it.

- [ ] **Step 4: Run no-call-site and full regression checks**

Use `rg` scans, focused pytest, full pytest, frontend type/build, and browser smoke. A deleted path is accepted only when all real callers have migrated.

- [ ] **Step 5: Prepare the checkpoint commit after explicit git approval**

Suggested message: `refactor(routedeck): retire duplicate Corpus contracts`

### Task 16: Complete verification, packaging, and context closeout

**Files:**
- Modify: `README.md`, `docs/route-deck-reference.md`, `docs/using-routedeck.md`, `docs/minimal-example.md`.
- Modify: `architecture/code-map.md`, component docs, `SYSTEM_FLOW_INDEX.md`, `test_index/README.md`.
- Modify: RouteDeck and SaaStoAgent `context.md`, logs, checkpoints, context history.
- Modify: package metadata/CI only as required by actual implementation.

**Interfaces:**
- Produces: verified framework release candidate and durable restart context.
- Consumes: all source, examples, conformance suites, and smoke evidence.

- [ ] **Step 1: Run Python framework suites**

```powershell
python -m pytest tests -q
```

Expected: all RouteDeck core, LangGraph, FastAPI, event, conformance, and anti-drift suites pass.

- [ ] **Step 2: Run React suites and package checks**

```powershell
cd react
npm ci
npm test
npm pack --dry-run
```

Expected: tests pass and package contents contain built/public files only.

- [ ] **Step 3: Run both example suites and clean-install checks**

Run each backend pytest suite, frontend test/build, and installation from a clean virtual environment. Live model execution without credentials must fail explicitly; with real configured credentials it must execute the real flow.

- [ ] **Step 4: Run Corpus regression and browser acceptance**

Ask for runtime location first. Verify health, state, typed operations, review, channel isolation, reconnect/replay, product surfaces, no hidden-route leakage, and the existing register-to-create-agent path. Report exact URLs and commands.

- [ ] **Step 5: Run architecture coverage and drift scans**

```powershell
python scripts/check_doc_coverage.py
git diff --check
```

Also scan framework/example source for Corpus, SaaStoAgent, Medusa, manual SSE framing, production fake models, and client-authoritative graph-state paths.

- [ ] **Step 6: Update context architecture with exact evidence**

Record command results, counts, example URLs, blockers, owning code-map rows, and no-op truth. Archive previous contexts per `work_prompt.md`.

- [ ] **Step 7: Prepare final checkpoint commit after explicit git approval**

Suggested message: `docs(routedeck): close out full-stack framework refactor`

## Plan Completion Criteria

- Both standalone examples run through public RouteDeck APIs and installed packages.
- Full Flow product code has no LangGraph/runtime/transport plumbing.
- Core Integration wraps an unchanged independently runnable existing graph.
- Both modes pass the same conformance suite.
- State is server-authoritative; dispatch is versioned and idempotent.
- Dispatch is claimed before executor invocation; the durable backend atomically
  commits public state, idempotent result, projection/terminal events, and
  outbox, and survives process reopen.
- Guards block before execution; review executes at most once.
- One application specification drives public nodes, flows/outcomes, operations, surfaces, validation, projection, and exported client contract.
- All channels use one typed event envelope and concrete payload schemas while
  maintaining visibility isolation.
- Event ordering, replay, deduplication, overflow, disconnect, and terminal failure semantics are tested.
- Product code never manually formats SSE.
- Corpus contains domain declarations and behavior but no generic framework mechanics.
- No active Entry aliases, pass-through Corpus framework types, `ACTION_TARGETS`, or hidden compatibility fallbacks remain.
- RouteDeck Python, React, examples, Corpus, browser, clean-install, architecture coverage, and context closeout checks pass.
