# RouteDeck Runtime-Boundary Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan slice-by-slice. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move reusable runtime assembly, LangGraph conversation driving, assistant-initiated turns, and conversation presentation behavior into RouteDeck while leaving Medusa responsible only for commerce configuration, business logic, graphs, prompts, and product UI.

**Architecture:** RouteDeck Core will expose one immutable runtime-services container and builder; the SQLAlchemy adapter will open and close durable resources; the LangGraph adapter will build the conversation driver from product-supplied graphs; and FastAPI will derive every HTTP plane from the same runtime. Medusa will inject its compiled app, bindings, session callbacks, market facts, graph factory, and Store API client without constructing generic runners, dependencies, drivers, or transport routes.

**Tech Stack:** Python 3.11+, Pydantic 2, FastAPI 0.136.3, SQLAlchemy 2, LangGraph 1.2.9, LangChain 1.3.13, React 19.2.7, TypeScript 7.0.2, Vitest 4.1.10, pnpm 11.7.0, Playwright 1.61.1, local Windows PowerShell, local Docker Desktop.

## Global Constraints

- Authoritative repository: `D:\Dev\AI Projects\routedeck`; do not use the former `agent-core` checkout.
- Runtime location is local Windows only. Do not probe or use the Mac mini or another remote host.
- Do not perform Git operations unless the user separately requests them. This plan contains no stage, commit, branch, merge, push, pull, reset, or rebase steps.
- Do not deploy. Any future deployment requires explicit confirmation that it will run without Git and separate approval.
- Do not introduce fixtures, synthetic commerce data, deterministic product responses, heuristic substitutes, fallback models, alternate providers, or canned assistant text in product paths.
- Test fixtures remain isolated under test or explicitly test-only E2E support paths.
- Required dependencies, graph contracts, model credentials, persistence, Store API behavior, and invariants fail visibly; no function silently switches execution paths.
- Real Medusa remains the commerce source of truth. Browser code never calls `/store/*` directly.
- Preserve all buyer-visible chat, surface, hybrid, navigation, checkout, private-form, review, placement, reconciliation, and confirmation behavior.
- Preserve `POST /api/routedeck/chat` and its public request/SSE behavior. Add the assistant-initiated turn as a distinct typed operation.
- Perform clean call-site migrations. Do not retain compatibility endpoints, aliases, wrappers, re-exports, or parallel old/new implementations.
- Do not split the product checkout feature, redesign the UI, change product copy, replace the Navgraph, change Medusa configuration semantics, or broaden the refactor into unrelated modules.
- Do not run pre-change baseline suites or test after individual file moves. Build the complete slice first.
- At each slice boundary, run one focused gate covering that slice's behavior and immediate side effects; do not run unrelated packages.
- Run the all-up unit/type/build regression only once, after all five slices are assembled.
- The final browser acceptance is one live-model, real-Medusa checkout journey that deliberately mixes casual chat, direct surface actions, and hybrid state convergence.
- The successful final browser run must retain a Playwright video and copy it to `artifacts/routedeck-runtime-boundary/human-checkout-flow.webm`.
- Test count and global coverage percentages are not progress measures.
- A protected demo `Reset` and the consolidated release harness require a separate approval checkpoint because they mutate local protected data.

---

## Current-State Evidence And Boundary Verdict

The following evidence comes from the current source, not historical plans:

- `examples/medusa-agent/backend/medusa_agent/runtime_factory.py` constructs `RouteDeckOperationRunner`, `RouteDeckNavigationRunner`, SQLAlchemy persistence, and the product-named `MedusaRuntime` container.
- `examples/medusa-agent/backend/medusa_agent/runtime.py` constructs the clock, notifier, codec, `RouteDeckDependencies`, configured projector, and live/test model objects.
- `examples/medusa-agent/backend/medusa_agent/agent_driver.py` owns generic `astream_events` traversal, model chunk handling, tool/review translation, durable turn extraction, and assistant-stream validation.
- `examples/medusa-agent/backend/main.py` constructs generic dependencies and drivers, exposes separate generic routers, and mounts a product entry router.
- `examples/medusa-agent/backend/medusa_agent/api/entry.py`, `entry_conversation.py`, and `frontend/src/app/conversationEntryClient.ts` duplicate a conversation mutation path for the initial assistant greeting.
- `packages/react/src/conversation/transitions.ts` accepts a generic update port and interprets events through reducer-shaped transitions instead of named presentation actions.
- `scripts/check_boundaries.py::check_shared_runner` requires the product runtime factory, `MedusaRuntime`, navigation runner, and `RouteDeckDependencies`; therefore the executable boundary report can bless the architecture this refactor must remove.
- Confirmed responsibility hotspots are `routedeck_core/app/compiler.py` (867 lines), `routedeck_fastapi/router.py` (536), `routedeck_sqlalchemy/store.py` (699), `packages/core/src/contracts/decode.ts` (1,125), `packages/core/src/store/store.ts` (564), and Medusa `medusa/client/http.py` (551).

**Boundary verdict:** ADR-004's consumer-driven product boundary remains correct, but ADR-005's statement that product `runtime_factory.py` assembles RouteDeck infrastructure is now too weak. Record a new ADR-006 that partially supersedes that clause and the approved design's product-owned entry/driver placement. Do not rewrite ADR-005 as if the decision never existed.

## Final Package And File Layout

```text
routedeck_core/
  runtime.py                       # runtime ports, services/container, builder
  runtime_defaults.py              # UTC clock, in-process wakeup notifier, IDs
  ports/codec.py                    # framework-neutral SensitiveCodec protocol
  projection/configured.py         # per-session configured projector

routedeck_sqlalchemy/
  application_runtime.py           # durable resources + fail-closed runtime opener
  store.py                         # canonical SqlAlchemySessionStore facade
  store_parts/
    lifecycle.py                   # open/close/read/write/recovery ownership
    sessions.py                    # create/load/request lookup transactions
    turns.py                       # turn and child-attempt lease transactions
    supervision.py                 # review and execution transactions
    commits.py                     # state/turn/attempt/supervision commits
    events.py                      # durable event reads
    private_forms.py               # encrypted private-blob transactions
    maintenance.py                 # expiration and abandoned-turn cleanup

routedeck_langgraph/
  agent_driver.py                  # generic graph factory + event translation
  conversation.py                  # user and assistant turn extraction

routedeck_fastapi/
  runtime.py                       # runtime provider and dependency derivation
  router.py                        # one canonical RouteDeck router
  routes/
    contract.py
    sessions.py
    operations.py
    conversation.py
    events.py
    private_forms.py
    inspection.py

packages/react/src/conversation/
  presentation.ts                 # presentation state + named actions
  useRouteDeckConversation.ts     # network orchestration and event coordination

packages/core/src/contracts/
  decode.ts                       # canonical public barrel
  json.ts
  projection.ts
  events.ts
  operations.ts
  frontend.ts
  privateForms.ts
  inspection.ts

packages/core/src/store/
  store.ts                        # public factory and coordinator composition
  bootstrap.ts
  synchronization.ts
  operations.ts
  lifecycle.ts
  navigation.ts                   # existing ownership retained
  events.ts                       # existing ownership retained
  routing.ts                      # existing ownership retained

examples/medusa-agent/backend/medusa_agent/
  runtime.py                      # product configuration and live composition call
  session.py                      # BuyerMarket, session factory, cart initializer
  agent.py                        # prompts, models, graphs, product graph factory
  bindings.py                     # product binding factory over one compiled app
  api/health.py                   # product liveness/readiness only
  medusa/client/http.py           # canonical MedusaStoreClient facade
  medusa/client/resources/
    base.py
    catalog.py
    cart.py
    checkout.py
    orders.py
```

## Locked Public Interfaces

### Core runtime

```python
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

SessionFactory = Callable[
    [CompiledRouteDeckApp, str],
    RouteDeckSession | Awaitable[RouteDeckSession],
]
SessionInitializer = Callable[
    ["RouteDeckRuntimeServices", SessionSnapshot],
    SessionSnapshot | Awaitable[SessionSnapshot],
]
PublicKeyValidatorFactory = Callable[
    [RouteDeckSession], PublicRouteKeyValidator | None
]

class RouteDeckRuntimeLifecycle(Protocol):
    async def close(self) -> None: ...

class RouteDeckAgentDriverFactory(Protocol):
    def create(
        self, services: "RouteDeckRuntimeServices"
    ) -> RouteDeckAgentDriver | None: ...

@dataclass(frozen=True)
class RouteDeckRuntimeServices:
    app: BoundRouteDeckApp
    store: RouteDeckSessionStore
    clock: Clock
    notifier: RouteDeckNotifier
    id_factory: Callable[[str], str]
    runner: RouteDeckOperationRunner
    navigation: RouteDeckNavigationRunner
    projector: ConfiguredSessionProjector

@dataclass(frozen=True)
class RouteDeckRuntime:
    services: RouteDeckRuntimeServices
    private_form_codec: SensitiveCodec
    session_factory: SessionFactory
    session_initializer: SessionInitializer
    agent_driver: RouteDeckAgentDriver | None
    lifecycle: RouteDeckRuntimeLifecycle

    async def close(self) -> None:
        await self.lifecycle.close()
```

`build_routedeck_runtime(...)` constructs exactly one operation runner, passes that instance to navigation, builds the configured projector, and returns the immutable container. Conversation support is an explicit optional capability: when a driver factory is supplied, the builder calls it exactly once after services exist; when it is explicitly absent, the runtime exposes `agent_driver=None` and FastAPI returns visible dependency-unavailable behavior for conversation writes. There is no dynamic `getattr(..., "close")` path.

### SQLAlchemy runtime opener

```python
@dataclass(frozen=True)
class SqlAlchemyRuntimeResources:
    store: SqlAlchemySessionStore
    codec: FernetSensitiveCodec

ApplicationFactory = Callable[
    [SqlAlchemyRuntimeResources], BoundRouteDeckApp
]

async def open_sqlalchemy_routedeck_runtime(
    *,
    compiled_app: CompiledRouteDeckApp,
    application_factory: ApplicationFactory,
    session_factory: SessionFactory,
    session_initializer: SessionInitializer,
    public_key_validator_factory: PublicKeyValidatorFactory,
    agent_driver_factory: RouteDeckAgentDriverFactory | None,
    database_url: str,
    encryption_key: str | bytes,
    instance_id: str,
    review_ttl: timedelta,
    resume_capability_ttl: timedelta,
    default_session_id: str,
    retention_policy: RouteDeckRetentionPolicy | None = None,
    busy_timeout: timedelta = timedelta(seconds=5),
    worker_count: int = 1,
    clock: Clock | None = None,
    notifier: RouteDeckNotifier | None = None,
    id_factory: Callable[[str], str] | None = None,
) -> RouteDeckRuntime: ...
```

The optional clock/notifier/ID arguments are explicit test or host overrides. When omitted before any resource is opened, the builder selects the documented RouteDeck defaults. `agent_driver_factory=None` explicitly declares a runtime without conversation execution; it is not selected in response to a graph/model failure. A supplied dependency that fails is never replaced by a default.

### Typed conversation triggers and LangGraph driver

```python
@dataclass(frozen=True)
class UserMessageTrigger:
    message: str
    user_turn: FinalizedConversationTurn

@dataclass(frozen=True)
class AssistantInitiatedTrigger:
    pass

RouteDeckConversationTrigger: TypeAlias = (
    UserMessageTrigger | AssistantInitiatedTrigger
)

@dataclass(frozen=True)
class RouteDeckAgentTurn:
    session_id: str
    request_id: str
    lease: TurnLease
    trigger: RouteDeckConversationTrigger

@dataclass(frozen=True)
class RouteDeckLangGraphGraphs:
    user_message: LangGraphEventStream
    assistant_initiated: LangGraphEventStream
    ignored_event_tags: frozenset[str]

GraphFactory = Callable[
    [RouteDeckRuntimeServices], RouteDeckLangGraphGraphs | None
]

@dataclass(frozen=True)
class RouteDeckLangGraphDriverFactory:
    graph_factory: GraphFactory

    def create(
        self, services: RouteDeckRuntimeServices
    ) -> RouteDeckAgentDriver | None: ...
```

User-message extraction requires exactly one matching `HumanMessage` marker and retains the current user turn. Assistant-initiated extraction sends no `HumanMessage`, permits exactly one streamed non-tool assistant result, and commits only that assistant turn. Tool calls or review output from the assistant-initiation graph fail the adapter contract.

### FastAPI assistant request

```python
class AssistantTurnRequest(RouteDeckRequestModel):
    request_id: str = Field(min_length=1, max_length=256)
    expected_session_version: int = Field(ge=0)
```

The endpoint is `POST /api/routedeck/conversation/assistant-turn` and returns the same SSE frame family as chat, except it emits no `user_message` frame.

### React presentation actions

```typescript
export interface ConversationPresentationActions {
  beginTurn(): void;
  restoreSnapshot(turns: readonly AgentHistoryTurn[], requestId: string): void;
  showUserMessage(event: Extract<AgentStreamEvent, { type: "user_message" }>): void;
  appendAssistantText(requestId: string, content: string): void;
  resetAssistantText(requestId: string): void;
  finalizeAssistant(requestId: string, turnId: string): void;
  requireReview(review: AgentReviewRequired): void;
  removeRequest(requestId: string): void;
  completeTurn(status: "idle" | "review_required"): void;
  failTurn(error: AgentChatError, pending: AgentPendingRequest | null): void;
  clearFailure(): void;
}
```

The presentation layer owns ephemeral rendered messages, status, error, review, and pending-request display only. `RouteDeckObservableState` remains the canonical frontend projection/session authority.

## Failure, Replay, Concurrency, And Cleanup Semantics

- Both user and assistant turns acquire `TurnOwnerKind.CHAT`, making product surfaces inert through the existing canonical interaction handshake.
- Fingerprints include an explicit trigger discriminator: `{"kind":"user_message","message":...}` or `{"kind":"assistant_initiated"}`.
- Reusing the same request ID with the same trigger and payload replays durable SSE frames without invoking a graph.
- Reusing an ID with a different trigger or message returns `409 request_id_reused`.
- A stale version returns `409 version_conflict` before graph invocation.
- The assistant-initiation path creates no synthetic user turn and never interprets an empty message as a trigger.
- Successful completion atomically persists finalized conversation turns and the mutation record before `assistant_end`.
- Graph or stream failure interrupts the turn, persists an interrupted marker, and emits `chat_error` plus `stream_end: turn_interrupted`.
- If interruption persistence fails, emit only `stream_end: outcome_unknown`; the browser retains the exact request for explicit retry or resynchronization.
- Cancellation shields interruption persistence and closes the LangGraph async event stream.
- Review behavior remains available for user turns. Assistant-initiation graphs must be no-tool and cannot stage review.
- Two concurrent greeting attempts use the existing lease/version rules. The losing browser reloads canonical conversation after a visible conflict; it does not invent a greeting.
- SQLAlchemy resources close on runtime-build failure and through the explicit runtime lifecycle. No alternate store, codec, model, notifier, or cached result is selected after failure.

---

## Five Implementation Slices

The five headings below are the only execution/review boundaries. The work packages inside a slice are one coordinated change and do not receive separate test cycles. Tests may be added or updated while implementing, but they are executed only at the slice gate.

### Slice 1: Framework Runtime And Generic LangGraph Driver

**Outcome:** RouteDeck owns durable runtime assembly and generic LangGraph event driving. Medusa supplies only its compiled/bound app, session callbacks, graph factory, models/prompts/policy, market facts, commerce adapter, readiness, and product UI. The existing product entry route may remain only until Slice 2, but it must consume the new generic driver; the old product runtime factory and product driver are deleted in this slice.

#### Work package 1A: Framework runtime and durable assembly

**Files:**
- Create: `decisions/ADR-006-framework-owned-runtime-and-conversation-boundary.md`
- Create: `routedeck_core/runtime.py`
- Create: `routedeck_core/runtime_defaults.py`
- Create: `routedeck_core/ports/codec.py`
- Create: `routedeck_core/projection/configured.py`
- Create: `routedeck_sqlalchemy/application_runtime.py`
- Create: `routedeck_fastapi/runtime.py`
- Create: `tests/state/test_runtime_builder.py`
- Modify: `decisions/ADR-005-operation-centric-state-and-consumer-structure.md`
- Modify: `decisions/README.md`
- Modify: `routedeck_core/__init__.py`
- Modify: `routedeck_core/ports/__init__.py`
- Modify: `routedeck_core/projection/__init__.py`
- Modify: `routedeck_sqlalchemy/__init__.py`
- Modify: `routedeck_fastapi/dependencies.py`
- Modify: `routedeck_fastapi/__init__.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/bindings.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/session.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/runtime.py`
- Modify: `examples/medusa-agent/backend/main.py`
- Modify: `examples/medusa-agent/backend/tests/support/runtime.py`
- Modify: `examples/medusa-agent/backend/tests/contract/test_runner_binding.py`
- Modify: `examples/medusa-agent/backend/tests/contract/test_home_session.py`
- Modify: `tests/sqlite/test_persistent_runtime_smoke.py`
- Delete: `examples/medusa-agent/backend/medusa_agent/runtime_factory.py`

**Interfaces:**
- Consumes: `BoundRouteDeckApp`, `RouteDeckSessionStore`, `Clock`, `RouteDeckNotifier`, `RegisteredOperationExecutor`, `RouteDeckOperationRunner`, `RouteDeckNavigationRunner`, `ProjectionProjector`, and `FernetSensitiveCodec`.
- Produces: the exact runtime interfaces under **Locked Public Interfaces**, `ConfiguredSessionProjector.project(session)`, `open_sqlalchemy_routedeck_runtime(...)`, and `dependencies_from_runtime(runtime, cookie, sse)`.

- [x] **Work 1: Prepare focused runtime ownership coverage**

```python
def test_runtime_builder_reuses_one_runner_for_navigation() -> None:
    runtime = build_test_routedeck_runtime()
    assert runtime.services.navigation.operation_runner is runtime.services.runner
    assert runtime.services.projector.app is runtime.services.app.app

@pytest.mark.asyncio
async def test_runtime_close_uses_the_explicit_lifecycle_once() -> None:
    runtime, lifecycle = build_test_routedeck_runtime_with_lifecycle()
    await runtime.close()
    assert lifecycle.close_calls == 1
```

Define both named test factories locally in `tests/state/test_runtime_builder.py`. They must use an explicit in-memory test store, fixed aware clock, recording notifier, sequential ID factory, compiled/bound test app, and a `RecordingLifecycle` whose `close()` only increments `close_calls`; they must call the production `build_routedeck_runtime` rather than recreating its assembly.

Update `test_runner_binding.py` so failed initial cart creation calls a product `initialize_medusa_session(services, snapshot)` callback rather than constructing `MedusaRuntime`. Update the persistent smoke to open through `open_sqlalchemy_routedeck_runtime`.

- [x] **Work 2: Implement the core runtime, defaults, codec port, and configured projector**

Implement the locked interfaces verbatim. `build_routedeck_runtime` must perform this single path:

```python
runner = RouteDeckOperationRunner(
    app=app,
    store=store,
    executor=RegisteredOperationExecutor(),
    clock=clock,
    notifier=notifier,
    id_factory=id_factory,
    review_ttl=review_ttl,
    resume_capability_ttl=resume_capability_ttl,
    default_session_id=default_session_id,
)
navigation = RouteDeckNavigationRunner(
    app=app,
    store=store,
    operation_runner=runner,
    clock=clock,
    notifier=notifier,
    id_factory=id_factory,
    public_key_validator_factory=public_key_validator_factory,
)
services = RouteDeckRuntimeServices(
    app=app,
    store=store,
    clock=clock,
    notifier=notifier,
    id_factory=id_factory,
    runner=runner,
    navigation=navigation,
    projector=ConfiguredSessionProjector(
        app=app.app,
        clock=clock,
        public_key_validator_factory=public_key_validator_factory,
    ),
)
```

Move `UtcClock`, the in-process cursor-aware notifier, and `_new_runtime_id` into `runtime_defaults.py`. Validate non-empty ID kinds. Move the duplicate `SensitiveCodec` protocol into Core and import it from FastAPI and SQLAlchemy.

- [x] **Work 3: Implement fail-closed SQLAlchemy opening and FastAPI derivation**

`open_sqlalchemy_routedeck_runtime` must compile no product app, infer no market, and know no Medusa symbols. It creates the codec and store, invokes the product `application_factory(SqlAlchemyRuntimeResources(...))`, validates that the returned bound app owns `compiled_app`, builds the runtime, and closes the store in `except BaseException` before re-raising.

`dependencies_from_runtime` maps the same service instances into `RouteDeckDependencies`; it does not construct runner, navigation, projector, notifier, codec, or session callbacks.

- [x] **Work 4: Migrate Medusa assembly and delete the product runtime factory**

Change `bind_medusa_app` to accept `app: CompiledRouteDeckApp` and never call `compile_medusa_app_spec()` internally. Change `create_medusa_session` to accept that compiled app explicitly. Add:

```python
async def initialize_medusa_session(
    services: RouteDeckRuntimeServices,
    created: SessionSnapshot,
) -> SessionSnapshot:
    result = await services.runner.run(
        OperationRequest(
            session_id=created.session_id,
            request_id=initial_cart_request_id(created.session_id),
            expected_session_version=created.session_version,
            operation_id=CART_CREATE.id,
            source=OperationSource.SYSTEM,
        )
    )
    if (
        result.disposition is not OperationDisposition.COMPLETED
        or result.outcome != MedusaOutcomeType.CREATED
    ):
        raise RuntimeError("Medusa session initialization did not prove cart creation.")
    return await services.store.load(created.session_id)
```

`runtime.py` compiles once, resolves real market facts, and supplies callbacks to the SQLAlchemy opener. Remove `MedusaRuntime`, `MedusaSessionProjector`, `project_medusa_session`, duplicate codec construction, and dynamic store closing.

For this slice only, pass `agent_driver_factory=None` and leave the single existing Medusa conversation driver wired exactly where it already runs. Do not add an adapter alias or a second driver. Work package 1B moves that unchanged conversation responsibility into `routedeck_langgraph`, supplies the final driver factory to the runtime, and removes the product construction in the same slice. The product path therefore remains usable between slices without running parallel old/new drivers.

#### Work package 1B: Product-neutral LangGraph conversation driver

**Files:**
- Create: `routedeck_langgraph/agent_driver.py`
- Create: `tests/test_langgraph_agent_driver.py`
- Modify: `routedeck_core/ports/agent_driver.py`
- Modify: `routedeck_core/ports/__init__.py`
- Modify: `routedeck_core/runtime.py`
- Modify: `routedeck_langgraph/conversation.py`
- Modify: `routedeck_langgraph/__init__.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/agent.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/runtime.py`
- Modify: `examples/medusa-agent/backend/main.py`
- Modify: `examples/medusa-agent/e2e/backend-support/routedeck_release_scripted_agent.py`
- Modify: `examples/medusa-agent/backend/tests/contract/test_agent_middleware.py`
- Modify: `examples/medusa-agent/backend/tests/contract/test_chat_error_logging.py`
- Modify: `examples/medusa-agent/backend/tests/integration/test_agent_chat_flow.py`
- Delete: `examples/medusa-agent/backend/medusa_agent/agent_driver.py`

**Interfaces:**
- Consumes: `RouteDeckRuntimeServices`, `RouteDeckAgentDriverFactory`, typed triggers, `RouteDeckInvocationContext`, and product-created LangGraph agents.
- Produces: `LangGraphEventStream`, `RouteDeckLangGraphGraphs`, `RouteDeckLangGraphDriverFactory`, and `RouteDeckLangGraphAgentDriver` from the locked interface.

- [x] **Work 1: Move behavioral coverage to the adapter boundary**

Add adapter-owned cases proving:

```python
@pytest.mark.asyncio
async def test_user_graph_streams_and_extracts_one_durable_suffix() -> None:
    events = [event async for event in driver.stream(user_agent_turn())]
    assert [type(event) for event in events] == [
        AssistantTextDelta,
        AgentTurnCompleted,
    ]
    completed = events[-1]
    assert [turn.role for turn in completed.turns] == [
        ConversationRole.USER,
        ConversationRole.ASSISTANT,
    ]

@pytest.mark.asyncio
async def test_ignored_product_event_tags_never_leak_model_text() -> None:
    events = [event async for event in tagged_driver().stream(user_agent_turn())]
    assert all(
        not isinstance(event, AssistantTextDelta)
        or "policy sentinel" not in event.content
        for event in events
    )
```

Move event-translation expectations out of Medusa contract tests. Keep FastAPI interruption/log-sanitization assertions in `test_chat_error_logging.py`, using a small fake `RouteDeckAgentDriver`.

- [x] **Work 2: Move the event translator without Medusa imports**

Move the complete `astream_events` translation algorithm into `routedeck_langgraph/agent_driver.py`. Replace the concrete runner field with `id_factory: Callable[[str], str]`, and replace `TURN_POLICY_EVENT_TAG` import with `ignored_event_tags: frozenset[str]`.

The driver selects the graph strictly by trigger type:

```python
graph = (
    self.graphs.user_message
    if isinstance(turn.trigger, UserMessageTrigger)
    else self.graphs.assistant_initiated
)
```

Split trigger-specific input/extraction into named private methods; do not add a generic recovery branch. Keep parallel-tool rejection, assistant reset, review translation for user turns, final-stream verification, and async stream closure.

- [x] **Work 3: Let the runtime builder construct the driver from product graphs**

The product graph factory returns either an explicit `RouteDeckLangGraphGraphs` or `None` when live credentials are absent. Live and `scripted-test-only` selection remains product-owned and fail-closed. The adapter factory constructs the generic driver; `main.py` and all Medusa production modules must not call `RouteDeckLangGraphAgentDriver(...)`.

The scripted E2E module returns the two graphs through one graph-factory function and keeps all deterministic responses under its explicit test-only path.

#### Slice 1 gate — run once after both work packages are complete

- [x] Run only the runtime, adapter, persistence, and immediate Medusa host proofs:

```powershell
python -m pytest tests/state/test_runtime_builder.py tests/sqlalchemy tests/sqlite/test_persistent_runtime_smoke.py tests/test_langgraph_agent_driver.py tests/test_langgraph_model_context.py tests/test_langgraph_policy_prompt.py examples/medusa-agent/backend/tests/contract/test_runner_binding.py examples/medusa-agent/backend/tests/contract/test_home_session.py examples/medusa-agent/backend/tests/contract/test_agent_middleware.py examples/medusa-agent/backend/tests/contract/test_chat_error_logging.py examples/medusa-agent/backend/tests/integration/test_agent_chat_flow.py -q
```

Expected: pass. One framework-built runner is shared with navigation; SQLAlchemy resources close explicitly; the product constructs neither generic runners nor a conversation driver; chat still streams through the product graph. Do not run the full backend suite here.

---

### Slice 2: Assistant-Initiated Turn And React Named Actions

**Outcome:** A typed RouteDeck assistant-turn endpoint replaces the Medusa entry transport, while React uses named presentation actions instead of generic reducer-shaped transitions. Automatic greeting, chat streaming, retry/resync, interruption, and canonical observable state remain intact.



#### Work package 2A: Typed assistant-initiated conversation turn

**Files:**
- Create: `tests/fastapi/test_conversation_turns.py`
- Modify: `routedeck_fastapi/contracts.py`
- Modify: `routedeck_fastapi/conversation.py`
- Modify: `routedeck_fastapi/conversation_replay.py`
- Modify: `routedeck_fastapi/conversation_stream.py`
- Modify: `routedeck_fastapi/dependencies.py`
- Modify: `routedeck_fastapi/router.py`
- Modify: `routedeck_fastapi/runtime.py`
- Modify: `routedeck_fastapi/__init__.py`
- Modify: `packages/core/src/conversation/types.ts`
- Modify: `packages/core/src/conversation/codec.ts`
- Modify: `packages/core/src/conversation/client.ts`
- Modify: `examples/medusa-agent/backend/main.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/api/__init__.py`
- Modify: `examples/medusa-agent/backend/tests/integration/test_entry_conversation.py`
- Modify: `examples/medusa-agent/backend/tests/integration/test_agent_chat_flow.py`
- Modify: `examples/medusa-agent/frontend/src/main.tsx`
- Modify: `examples/medusa-agent/frontend/src/tests/chat-client-reliability.test.ts`
- Modify: `tests/test_anti_drift_boundaries.py`
- Delete: `routedeck_fastapi/conversation_dependencies.py`
- Delete: `examples/medusa-agent/backend/medusa_agent/api/entry.py`
- Delete: `examples/medusa-agent/backend/medusa_agent/entry_conversation.py`
- Delete: `examples/medusa-agent/frontend/src/app/conversationEntryClient.ts`

**Interfaces:**
- Consumes: `RouteDeckRuntime.agent_driver`, typed core triggers, existing mutation store, turn runner, SSE encoding, and frontend conversation client.
- Produces: `AssistantTurnRequest`, `stream_agent_turn(...)`, `conversation_fingerprint(trigger)`, `streamAssistantTurn(request, signal)`, and one runtime-derived router provider.

- [x] **Work 1: Prepare generic lifecycle, replay, and collision coverage**

```python
@pytest.mark.asyncio
async def test_assistant_turn_persists_without_a_user_message(client, runtime) -> None:
    response = await client.post(
        "/api/routedeck/conversation/assistant-turn",
        json={"request_id": "entry-1", "expected_session_version": 1},
    )
    assert response.status_code == 200
    assert [event["event"] for event in sse_events(response.text)] == [
        "stream_start",
        "conversation_snapshot",
        "assistant_delta",
        "assistant_end",
        "stream_end",
    ]
    snapshot = await runtime.services.store.load(runtime_session_id(client))
    assert [turn.role for turn in snapshot.state.conversation] == [
        ConversationRole.ASSISTANT
    ]

@pytest.mark.asyncio
async def test_chat_request_id_cannot_be_reused_for_assistant_turn(client) -> None:
    await post_completed_chat(client, request_id="shared-id")
    response = await client.post(
        "/api/routedeck/conversation/assistant-turn",
        json={"request_id": "shared-id", "expected_session_version": 1},
    )
    assert response.status_code == 409
    assert response.json()["failure"]["code"] == "request_id_reused"
```

Define the `client`/`runtime` fixtures and `sse_events`, `runtime_session_id`, and `post_completed_chat` helpers in this new test module by extracting the existing ASGI client and SSE parsing arrangements from `tests/fastapi/test_transport_smoke.py` and `examples/medusa-agent/backend/tests/integration/test_agent_chat_flow.py`. The helpers may arrange inputs only; they must call the production router, runtime, store, and chat endpoint and contain no product result logic.

- [x] **Work 2: Generalize the conversation lifecycle around typed triggers**

Replace chat-only internal request handling with one `ConversationTurnRequest` carrying request ID, expected version, and the typed trigger. Keep `/chat` request validation unchanged and translate it to `UserMessageTrigger`; translate the new endpoint to `AssistantInitiatedTrigger`.

Build fingerprints exactly as:

```python
def conversation_fingerprint(trigger: RouteDeckConversationTrigger) -> str:
    payload = (
        {"kind": "user_message", "message": trigger.message}
        if isinstance(trigger, UserMessageTrigger)
        else {"kind": "assistant_initiated"}
    )
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
```

Only the user branch creates and emits a user turn. Both branches share lease, snapshot, replay, completion, interruption, logging, and terminal SSE code.

- [x] **Work 3: Derive all HTTP planes from one runtime provider**

Add `agent_driver` to runtime-derived dependencies and remove `RouteDeckConversationDependencies`. Replace the two generic router inclusions in `main.py` with one `create_routedeck_router_from_runtime_provider(...)`. The product host keeps CORS, health/readiness, lifespan, and runtime close only.

- [x] **Work 4: Add the generic TypeScript assistant client and migrate bootstrap**

Add:

```typescript
export interface AgentAssistantTurnRequest {
  request_id: string;
  expected_session_version: number;
}

export interface RouteDeckAgentClient {
  loadConversation(signal?: AbortSignal): Promise<readonly AgentHistoryTurn[]>;
  stream(request: AgentChatRequest, signal?: AbortSignal): AsyncIterable<AgentStreamEvent>;
  streamAssistantTurn(
    request: AgentAssistantTurnRequest,
    signal?: AbortSignal,
  ): AsyncIterable<AgentStreamEvent>;
}
```

`main.tsx` loads canonical history, consumes `streamAssistantTurn` only when history is empty, requires `assistant_end` plus `stream_end: completed`, synchronizes to the returned versions, and reloads conversation. A conflict triggers a canonical conversation reload; other failures remain visible bootstrap failures.

- [x] **Work 5: Delete the product entry plane**

Delete `routedeck_fastapi/conversation_dependencies.py`, the Medusa entry router/helper, and `conversationEntryClient.ts` after all call sites use the generic runtime route and client. Remove their exports and endpoint expectations; add no alias, forwarding endpoint, or compatibility response.

#### Work package 2B: Named React presentation actions

**Files:**
- Create: `packages/react/src/conversation/presentation.ts`
- Modify: `packages/react/src/conversation/useRouteDeckConversation.ts`
- Modify: `packages/react/src/index.ts`
- Modify: `examples/medusa-agent/frontend/src/tests/agent-stream-reliability.test.tsx`
- Modify: `examples/medusa-agent/frontend/src/tests/app-shell.test.tsx`
- Delete: `packages/react/src/conversation/state.ts`
- Delete: `packages/react/src/conversation/transitions.ts`

**Interfaces:**
- Consumes: `AgentStreamEvent`, `AgentHistoryTurn`, `AgentChatError`, `AgentReviewRequired`, and the existing synchronization callback.
- Produces: `ConversationPresentationState`, `ConversationPresentationActions`, and `useConversationPresentation(initialConversation)` matching the locked named-action interface.

- [x] **Work 1: Update focused coverage for named presentation behavior**

Retain the existing tests for late snapshots, partial assistant replacement, exact retry identity, interruption, outcome unknown, cancellation, and synchronization. Add one focused assertion that a reset removes only the active streaming assistant and leaves finalized history intact.

```typescript
expect(result.current.messages).toEqual([
  expect.objectContaining({ id: "durable-assistant", status: "finalized" }),
]);
```

- [x] **Work 2: Implement one presentation state and named actions**

`presentation.ts` owns the former message helpers and all React setters behind named methods. It exports no generic `dispatch`, `reduce`, `applyEvent`, transition callback, or action-object union. `useRouteDeckConversation.ts` performs the explicit SSE `switch` and calls a named method for each event.

Keep `AbortController`, retained exact request, retry, discard, resync, and client iteration in `useRouteDeckConversation.ts`; those are network lifecycle responsibilities, not presentation state.

- [x] **Work 3: Delete the reducer-shaped presentation modules**

Delete `packages/react/src/conversation/state.ts` and `packages/react/src/conversation/transitions.ts` after all imports use `presentation.ts`. Remove the old generic transition exports; do not retain wrappers or deprecated aliases.#### Slice 2 gate — run once after both work packages are complete

- [x] Run only assistant/chat transport and presentation side-effect proofs:

```powershell
python -m pytest tests/fastapi/test_conversation_turns.py examples/medusa-agent/backend/tests/integration/test_entry_conversation.py examples/medusa-agent/backend/tests/integration/test_agent_chat_flow.py tests/test_anti_drift_boundaries.py -q
pnpm --filter @routedeck/core test
pnpm --filter @routedeck/react typecheck
pnpm --filter @routedeck/react test
pnpm --filter @routedeck/medusa-agent exec vitest run --config vitest.config.ts src/tests/chat-client-reliability.test.ts src/tests/agent-stream-reliability.test.tsx src/tests/app-shell.test.tsx
```

Expected: pass. The greeting uses `POST /api/routedeck/conversation/assistant-turn`, persists no synthetic user turn, exact replay/collision semantics hold, and the old product entry and React transition modules are absent. Do not run Playwright in this slice.

---

### Slice 3: Python Responsibility Splits

**Outcome:** The core compiler, FastAPI router, and SQLAlchemy store are split behind their existing public facades. This is one Python maintainability slice: no new public API, endpoint, persistence behavior, or product behavior is introduced.



#### Work package 3A: Core compiler split

**Files:**
- Create: `routedeck_core/app/compiler_registry.py`
- Create: `routedeck_core/app/compiler_validation.py`
- Create: `routedeck_core/app/route_entries.py`
- Create: `routedeck_core/app/frontend_contract.py`
- Create: `routedeck_core/app/executable_paths.py`
- Modify: `routedeck_core/app/compiler.py`
- Test: `tests/app/test_app_composition.py`
- Test: `tests/app/test_feature_compiler.py`
- Test: `tests/app/test_route_entry_compiler.py`
- Test: `tests/app/test_compiled_contract.py`

**Interfaces:**
- Consumes: existing immutable specs and compiled contracts.
- Produces: unchanged public `compile_app(source_spec: ApplicationSpec) -> CompiledRouteDeckApp`; all new helpers remain package-internal and are not re-exported from `routedeck_core`.

- [x] **Work 1: Move exact function groups without semantic edits**

Move `_validate_feature_namespaces`, `_register_canonical`, and `_all_surfaces` to `compiler_registry.py`; all policy/reference/ownership/topology validation functions to `compiler_validation.py`; `_compile_route_entry_transitions` to `route_entries.py`; `_build_frontend_contract` and `_frontend_surface_slots` to `frontend_contract.py`; and executable path derivation/validation to `executable_paths.py`.

Leave the existing `compile_app` body as the single orchestration sequence. Its local dictionaries, validation order, `CompiledApplicationSpec`, `CompiledRouteDeckApp`, and return shape stay unchanged; only helper imports move:

```python
from .compiler_registry import (
    _all_surfaces,
    _register_canonical,
    _validate_feature_namespaces,
)
from .compiler_validation import (
    _validate_agent_policy_references,
    _validate_capability_references,
    _validate_feature_transition_ownership,
    _validate_hierarchy,
    _validate_node_references,
    _validate_operation_references,
    _validate_reachability,
    _validate_suggested_actions,
    _validate_surface_affordances,
    _validate_transitions,
)
from .executable_paths import (
    _derive_executable_test_paths,
    _validate_executable_test_paths,
)
from .frontend_contract import _build_frontend_contract
from .route_entries import _compile_route_entry_transitions
```

Do not add a second registry model; the existing local dictionaries remain the compile-time registry.

#### Work package 3B: FastAPI route-module split

**Files:**
- Create: `routedeck_fastapi/routes/__init__.py`
- Create: `routedeck_fastapi/routes/contract.py`
- Create: `routedeck_fastapi/routes/sessions.py`
- Create: `routedeck_fastapi/routes/operations.py`
- Create: `routedeck_fastapi/routes/conversation.py`
- Create: `routedeck_fastapi/routes/events.py`
- Create: `routedeck_fastapi/routes/private_forms.py`
- Create: `routedeck_fastapi/routes/inspection.py`
- Modify: `routedeck_fastapi/router.py`
- Modify: `routedeck_fastapi/__init__.py`
- Delete: `routedeck_fastapi/conversation.py`
- Test: `tests/fastapi/test_transport_smoke.py`
- Test: `tests/fastapi/test_conversation_turns.py`
- Test: `examples/medusa-agent/backend/tests/contract/test_chat_error_logging.py`

**Interfaces:**
- Consumes: one `RuntimeProvider`, request dependency resolution, existing response/private-form/session/SSE helpers, and mutation policy.
- Produces: only `create_routedeck_router_from_runtime_provider(provider, mutation_policy)` as the public construction entry point.

- [x] **Work 1: Update transport tests to target behavior rather than source-file decorators**

Retain endpoint, status, cookie, replay, SSE, private-form authorization, review, and inspect assertions. Remove assertions that require endpoints to live textually in `router.py` or a second conversation router.

- [x] **Work 2: Move endpoints by responsibility**

Each route module exports one factory. `router.py` composes them with the sole prefix and one resolved dependency provider:

```python
def create_routedeck_router_from_runtime_provider(
    provider: RuntimeProvider,
    *,
    mutation_policy: RouteDeckMutationPolicy | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/routedeck", tags=["routedeck"])
    request_policy = mutation_policy or SameOriginMutationPolicy()
    dependencies = dependency_provider_from_runtime(provider)
    router.include_router(create_contract_routes(dependencies))
    router.include_router(create_session_routes(dependencies, request_policy))
    router.include_router(create_operation_routes(dependencies, request_policy))
    router.include_router(create_conversation_routes(dependencies, request_policy))
    router.include_router(create_event_routes(dependencies))
    router.include_router(create_private_form_routes(dependencies, request_policy))
    router.include_router(create_inspection_routes(dependencies))
    return router
```

`router.py` owns the sole `/api/routedeck` prefix and includes contract, sessions, operations/reviews, conversation, events, private forms, and inspection exactly once. Delete the multi-argument `create_routedeck_router`, dependency-only `create_routedeck_router_from_provider`, and separate `create_routedeck_conversation_router` surfaces after all call sites move.

#### Work package 3C: SQLAlchemy transaction split

**Files:**
- Create: `routedeck_sqlalchemy/store_parts/__init__.py`
- Create: `routedeck_sqlalchemy/store_parts/lifecycle.py`
- Create: `routedeck_sqlalchemy/store_parts/sessions.py`
- Create: `routedeck_sqlalchemy/store_parts/turns.py`
- Create: `routedeck_sqlalchemy/store_parts/supervision.py`
- Create: `routedeck_sqlalchemy/store_parts/commits.py`
- Create: `routedeck_sqlalchemy/store_parts/events.py`
- Create: `routedeck_sqlalchemy/store_parts/private_forms.py`
- Create: `routedeck_sqlalchemy/store_parts/maintenance.py`
- Modify: `routedeck_sqlalchemy/store.py`
- Test: `tests/sqlalchemy/test_session_store.py`
- Test: `tests/sqlite/test_persistent_runtime_smoke.py`

**Interfaces:**
- Consumes: existing `SqlAlchemyStoreRuntime` and repository modules `sessions.py`, `turns.py`, `operations.py`, `commits.py`, `recovery.py`.
- Produces: unchanged public `SqlAlchemySessionStore`; transaction bodies move into responsibility objects and `store.py` delegates without adding another public store class.

- [x] **Work 1: Move lifecycle and transaction groups in dependency order**

Move open/close/read/write/recovery first; then session reads/creates; leases; review/execution; commits; events; private forms; cleanup. Each store-part object receives explicit repositories/runtime in its constructor. It must not recover by constructing a new database session runtime after failure.

The facade retains every current public method signature and delegates to the owning transaction service. For example:

```python
class SqlAlchemySessionStore:
    async def load(self, session_id: str) -> SessionSnapshot:
        return await self._sessions.load(session_id)

    async def close(self) -> None:
        await self._lifecycle.close()
```#### Slice 3 gate — run once after all three splits are complete

- [x] Run the Python behavior surfaces directly touched by the moves:

```powershell
python -m pytest tests/app tests/fastapi tests/sqlalchemy tests/sqlite/test_persistent_runtime_smoke.py tests/test_public_api.py examples/medusa-agent/backend/tests/contract/test_chat_error_logging.py examples/medusa-agent/backend/tests/integration/test_agent_chat_flow.py -q
```

Expected: pass. Public imports, HTTP/SSE behavior, persistence transactions, replay/concurrency behavior, and the Medusa host remain unchanged. Do not test each moved function group separately.

---

### Slice 4: TypeScript Core And Medusa HTTP Responsibility Splits

**Outcome:** TypeScript contract decoding and store coordination are split behind unchanged package APIs, and the Medusa Store client becomes a facade over typed resource modules. No second decoder, store, client, endpoint fallback, response coercion, or fixture-backed product path is introduced.



#### Work package 4A: TypeScript contract decoder split

**Files:**
- Create: `packages/core/src/contracts/json.ts`
- Create: `packages/core/src/contracts/projection.ts`
- Create: `packages/core/src/contracts/events.ts`
- Create: `packages/core/src/contracts/operations.ts`
- Create: `packages/core/src/contracts/frontend.ts`
- Create: `packages/core/src/contracts/privateForms.ts`
- Create: `packages/core/src/contracts/inspection.ts`
- Modify: `packages/core/src/contracts/decode.ts`
- Modify: `packages/core/src/contracts/decode.test.ts`

**Interfaces:**
- Consumes: generated contract types and existing strict decoder behavior.
- Produces: the same exported names from `contracts/decode.ts` and package root; no alternate decoder path or permissive coercion.

- [x] **Work 1: Extract strict primitives and domain decoders**

Move JSON types plus `expect*`, enum, array, ISO date, and `fail` helpers into `json.ts`. Move projection/location/value/entity/surface decoders to `projection.ts`; event decoder to `events.ts`; dispatch/failure result decoders to `operations.ts`; frontend contract to `frontend.ts`; private forms to `privateForms.ts`; inspection to `inspection.ts`.

Retain the canonical barrel:

```typescript
export * from "./json";
export * from "./projection";
export * from "./events";
export * from "./operations";
export * from "./frontend";
export * from "./privateForms";
export * from "./inspection";
```

#### Work package 4B: TypeScript store coordinator split

**Files:**
- Create: `packages/core/src/store/bootstrap.ts`
- Create: `packages/core/src/store/synchronization.ts`
- Create: `packages/core/src/store/operations.ts`
- Create: `packages/core/src/store/lifecycle.ts`
- Modify: `packages/core/src/store/store.ts`
- Modify: `packages/core/src/store/observable.test.ts`
- Test: `packages/core/src/client/reliability.test.ts`

**Interfaces:**
- Consumes: `RouteDeckObservableState`, existing routing/navigation/event coordinators, browser history, and `RouteDeckClient`.
- Produces: unchanged `createRouteDeckStore(config): RouteDeckStore`; named bootstrap, synchronization, operation, and lifecycle coordinators remain internal.

- [x] **Work 1: Extract coordinators with explicit ports**

`RouteDeckBootstrapCoordinator` owns resume/create/recovery and retained session-create attempts. `RouteDeckSynchronizationCoordinator` owns snapshots, resync, target synchronization, event reconciliation, and history synchronization callbacks. `RouteDeckOperationCoordinator` owns dispatch/review and post-result reconciliation. `RouteDeckStoreLifecycle` owns active/disposed checks and cleanup.

`store.ts` constructs those coordinators and returns the existing `RouteDeckStore` method table. It contains no copied bootstrap, synchronization, or operation algorithms after extraction.

#### Work package 4C: Medusa Store client resource split

**Files:**
- Create: `examples/medusa-agent/backend/medusa_agent/medusa/client/resources/__init__.py`
- Create: `examples/medusa-agent/backend/medusa_agent/medusa/client/resources/base.py`
- Create: `examples/medusa-agent/backend/medusa_agent/medusa/client/resources/catalog.py`
- Create: `examples/medusa-agent/backend/medusa_agent/medusa/client/resources/cart.py`
- Create: `examples/medusa-agent/backend/medusa_agent/medusa/client/resources/checkout.py`
- Create: `examples/medusa-agent/backend/medusa_agent/medusa/client/resources/orders.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/medusa/client/http.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/medusa/client/__init__.py`
- Modify: `examples/medusa-agent/backend/tests/unit/test_release_evidence.py`
- Modify: `tests/test_anti_drift_boundaries.py`
- Test: `examples/medusa-agent/backend/tests/integration/real_medusa/test_store_client.py`

**Interfaces:**
- Consumes: `StoreApiTransport`, strict wire decoders, typed result models, and evidence sink.
- Produces: unchanged `HttpMedusaStoreClient` satisfying `MedusaStoreClient`; endpoint templates may exist only in `transport.py` and the exact resource modules.

- [x] **Work 1: Extend the existing MockTransport proof across resource groups**

Use `test_release_evidence.py` to assert the facade delegates complete-cart and independent order reread through the orders resource while preserving measured evidence fields. Add one catalog and one checkout request assertion using `httpx.MockTransport`; label these explicitly as transport contract tests, not real-commerce validation.

- [x] **Work 2: Extract resources and keep one canonical facade**

`base.py` owns the current `_request` classification/decoding/evidence path. Catalog owns regions/products; cart owns cart and line items; checkout owns contact/shipping/payment; orders owns completion, order reread, and their evidence recording. `HttpMedusaStoreClient` constructs the resources and delegates every protocol method.

```python
class HttpMedusaStoreClient:
    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        evidence_sink: MedusaStoreEvidenceSink | None = None,
    ) -> None:
        base = MedusaResourceClient(
            settings,
            transport=transport,
            evidence_sink=evidence_sink,
        )
        self._catalog = CatalogResource(base)
        self._cart = CartResource(base)
        self._checkout = CheckoutResource(base)
        self._orders = OrdersResource(base)

    async def list_regions(self) -> RegionsResult:
        return await self._catalog.list_regions()

    async def complete_cart(self, cart_id: str) -> CompleteCartResult:
        return await self._orders.complete_cart(cart_id)
```

Do not add a second client implementation, endpoint fallback, response coercion, or fixture-driven product path.#### Slice 4 gate — run once after all three splits are complete

- [x] Run only the affected package contracts and Medusa transport/unit side effects:

```powershell
pnpm --filter @routedeck/core test
pnpm --filter @routedeck/core typecheck
pnpm --filter @routedeck/core build
pnpm --filter @routedeck/medusa-agent test
python -m pytest examples/medusa-agent/backend/tests/unit/test_release_evidence.py examples/medusa-agent/backend/tests/unit/features -q
```

Expected: pass. Package-root imports, strict decode failures, retry identity, resynchronization, browser history, and typed Store request/evidence behavior remain unchanged. The real Store path is exercised once in the final checkout instead of duplicated here.

---

### Slice 5: Enforced Boundaries, Authority Docs, And Recorded Acceptance

**Outcome:** Executable checks enforce the new ownership model, active documentation agrees with the final source, and one recorded local buyer journey proves the complete behavior against the live model and real Medusa.



#### Work package 5A: Executable runtime-ownership proof

**Files:**
- Modify: `scripts/check_boundaries.py`
- Modify: `tests/test_boundary_report.py`
- Modify: `tests/test_boundary_rules.py`
- Modify: `tests/test_anti_drift_boundaries.py`
- Modify: `tests/test_medusa_reference_slice0.py`
- Modify: `tests/test_release_harness.py`
- Modify: `examples/medusa-agent/backend/tests/contract/test_framework_imports.py`
- Modify: `examples/medusa-agent/scripts/release-summary.py`

**Interfaces:**
- Consumes: final framework/product layout and AST helpers already used by the boundary checker.
- Produces: `check_runtime_ownership(project_root) -> BoundaryCheck`, `runtime_ownership` in `REQUIRED_CHECK_NAMES`, and boundary report schema version `3`.

- [x] **Work 1: Replace source-text assumptions in boundary tests**

Update expected public endpoints to include `/api/routedeck/conversation/assistant-turn` and remove `/api/medusa-agent/conversation/entry`. Require all deleted paths to remain absent. Require the Medusa frontend to use only the generic conversation client.

- [x] **Work 2: Implement one focused runtime-ownership proof**

`check_runtime_ownership` must use AST evidence to assert:

```python
forbidden_product_constructors = {
    "RouteDeckOperationRunner",
    "RouteDeckNavigationRunner",
    "RouteDeckDependencies",
    "RouteDeckLangGraphAgentDriver",
}
```

It also asserts zero product `astream_events(...)` calls; exactly one runner and navigation constructor in the core runtime builder; navigation receives the local `runner`; the runtime services receive both; FastAPI derives its runner/navigation/projector/store from runtime services; and operations, conversation, private-form/event, and navigation modules consume those derived dependencies.

Keep `core_imports` as the reverse-import proof. Update product transport separation to inventory `routedeck_fastapi/routes/*.py`, require only the generic runtime router plus product health in `main.py`, and allow Store path literals only in the exact resource/transport owner set.

- [x] **Work 3: Update architectural review and release schemas**

Replace `shared_runner` with `runtime_ownership` in required check names, architectural-review evidence, release summary requirements, and release-harness fixtures. Rename the invariant to `generic_runtime_supplies_all_transport_planes`.

#### Work package 5B: Authority, reference, structure, and test documentation

**Files:**
- Modify: `README.md`
- Modify: `structure.md`
- Modify: `decisions/README.md`
- Modify: `docs/using-routedeck.md`
- Modify: `docs/route-deck-reference.md`
- Modify: `docs/medusa-agent-reference-app.md`
- Modify: `architecture/code-map.md`
- Modify: `architecture/components/core-runtime-contract.md`
- Modify: `architecture/components/langgraph-adapter.md`
- Modify: `architecture/components/react-runtime-debugger.md`
- Modify: `examples/medusa-agent/README.md`
- Modify: `test_index/README.md`

**Interfaces:**
- Consumes: final code and validation commands from Tasks 1-11.
- Produces: one consistent authority chain naming ADR-006, framework runtime ownership, generic driver/assistant route, named React actions, final module map, and current gates.

- [x] **Work 1: Remove stale ownership and endpoint statements**

Remove active-reference claims that `runtime_factory.py`, `MedusaRuntime`, `MedusaLangGraphAgentDriver`, product entry routes, or separate generic routers are current. Do not rewrite completed historical implementation plans; ADR-006 documents why current ownership changed.

- [x] **Work 2: Document the final runtime and adapter contracts**

The RouteDeck reference must describe the runtime container/builder and assistant turn. The Medusa reference must state that the product supplies compiled declarations/bindings, callbacks, graphs/prompts/models, market facts, Store client, readiness, and UI only. The code map must list the new runtime/route/store/resource owners and their exact test lanes.

- [x] **Work 3: Correct the stale documented LangGraph command and record slice gates**

Replace the nonexistent `tests/test_langgraph_adapter.py` command with:

```powershell
python -m pytest tests/test_langgraph_agent_driver.py tests/test_langgraph_model_context.py tests/test_langgraph_policy_prompt.py examples/medusa-agent/backend/tests/contract/test_agent_middleware.py -q
```

Add the assistant-turn test and runtime-ownership report commands. Keep real-Medusa and protected reset caveats explicit.

#### Work package 5C: One human-like checkout flow with retained video

**Files:**
- Create: `examples/medusa-agent/e2e/human-checkout-flow.spec.ts`
- Modify: `examples/medusa-agent/e2e/playwright.config.ts`
- Reuse: `examples/medusa-agent/e2e/support/buyer-flow.ts`
- Reuse: `examples/medusa-agent/e2e/support/fixtures.ts`
- Reuse: `examples/medusa-agent/e2e/support/test-data.ts`
- Evidence: `artifacts/routedeck-runtime-boundary/human-checkout-flow.webm`

**Interfaces:**
- Consumes: live `OPENAI_API_KEY`, the existing local protected Medusa stack, real catalog/cart/order state, the generic assistant-turn and chat endpoints, RouteDeck surfaces, review acceptance, and browser safety instrumentation.
- Produces: one outcome-driven Playwright scenario and one successful-run `.webm`; it does not add product behavior or a test-only model path.

- [x] **Work 1: Make successful video capture explicit and opt-in**

Keep ordinary test behavior unchanged, but make the final command able to retain video on success:

```typescript
function videoMode(): "on" | "retain-on-failure" {
  const value = process.env.ROUTEDECK_E2E_VIDEO;
  if (value === undefined) return "retain-on-failure";
  if (value !== "on") {
    throw new Error("ROUTEDECK_E2E_VIDEO must be 'on' when set.");
  }
  return value;
}

// In defineConfig({ use: { ... } }):
video: videoMode(),
```

- [x] **Work 2: Add one conversational, surface, and hybrid checkout scenario**

The test must use `ROUTEDECK_MODEL_MODE=live` and fail if it is absent or different. It must not skip to, invoke, or import the scripted agent.

Use these exact buyer interactions, while asserting outcomes rather than exact model prose:

```typescript
test("@human-checkout completes one live conversational hybrid purchase", async ({
  browserSafety,
  page,
}, testInfo) => {
  expect(process.env.ROUTEDECK_MODEL_MODE).toBe("live");
  test.setTimeout(360_000);
  const buyer = buyerForProject(testInfo.project.name);

  await page.goto("/");
  await expect(page.getByTestId("medusa-buyer-app")).toBeVisible();
  await expect(
    page.locator(
      '[data-agent-message="assistant"][data-agent-message-status="finalized"]',
    ),
  ).toHaveCount(1, { timeout: 150_000 });

  await sendCasualChat(
    page,
    "Hey — I'm looking for a black tee. Can you show me what you've got?",
    "/products",
  );

  await page
    .getByRole("link", { name: PRODUCT.catalogLinkLabel, exact: true })
    .click();
  await expectProduct(page);
  await selectVariantAndAddToCart(page);

  await sendCasualChat(
    page,
    "Nice, that works for me. Can you take me to my cart?",
    "/cart",
  );
  await expectCart(page);

  const confirmationUrl = await completeGuestCheckout(page, buyer);
  expect(new URL(confirmationUrl).pathname).toMatch(
    /^\/orders\/[^/]+\/confirmation$/,
  );
  await expect(
    page.getByRole("heading", { name: "Order confirmed", exact: true }),
  ).toBeVisible();
  browserSafety.assertClean();
});
```

`sendCasualChat` types with a small 25–40 ms per-character delay so the video is readable, waits for a successful `POST /api/routedeck/chat` SSE response, waits for the expected route, waits for the finalized assistant message count to increase, and fails on `[data-agent-chat-error]`. It does not inspect or force a specific tool call, inject model output, retry with alternate wording, or switch models. The surface click/add and later chat navigation must operate on the same session and the same real cart; checkout must pass through private contact entry, shipping, payment, review, explicit placement approval, independent confirmation reread, and final confirmation.

#### Slice 5 gate and final acceptance — run once, in this order

- [x] **Gate A: Validate boundary enforcement and active authority**

```powershell
python scripts/check_doc_coverage.py
python -m pytest tests/test_boundary_report.py tests/test_boundary_rules.py tests/test_anti_drift_boundaries.py tests/test_medusa_reference_slice0.py tests/test_release_harness.py tests/test_active_design_authority.py tests/test_public_api.py examples/medusa-agent/backend/tests/contract/test_framework_imports.py -q
python scripts/check_boundaries.py --json $env:TEMP\routedeck-boundaries.json
```

Expected: pass; the report has `schema_version: 3`, `status: pass`, `violation_count: 0`, and a passing `runtime_ownership` check.

- [x] **Gate B: Run the all-up non-real regression exactly once**

```powershell
python -m pytest tests examples/medusa-agent/backend/tests --ignore=examples/medusa-agent/backend/tests/integration/real_medusa -q
pnpm test
pnpm typecheck
pnpm build
```

Expected: pass. This is the only all-up unit/type/build run in the plan. Report exact pass/skip counts from current output.

- [x] **Gate C: Start the real local stack in live-model mode without resetting protected data**

Run on local Windows only:

```powershell
$env:ROUTEDECK_MODEL_MODE = "live"
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\demo-stack.ps1 -Action Up -Services all
```

Required smoke URLs:

- Frontend: `http://127.0.0.1:5198`
- Agent API: `http://127.0.0.1:8098`
- Product health: `http://127.0.0.1:8098/api/medusa-agent/health`
- Medusa: `http://127.0.0.1:9100`

A missing/invalid `OPENAI_API_KEY`, unavailable protected stack, unavailable real Store API, or unhealthy service is a hard blocker. Do not use the scripted graph, fixture commerce, another provider, or another host.

- [x] **Gate D: Run the single recorded human checkout**

```powershell
$env:ROUTEDECK_E2E_VIDEO = "on"
pnpm --filter @routedeck/medusa-agent-e2e exec playwright test --config playwright.config.ts --project=desktop-chromium human-checkout-flow.spec.ts
```

Expected: one test passes; initial assistant greeting, both casual chat turns, surface product/cart/checkout actions, explicit review approval, one real complete-cart mutation, independent order reread, and confirmation are visible. No direct browser `/store/*` request, HTTP failure, browser error, chat error, scripted model, or fallback occurs.

Do not separately run `scripted-agent.spec.ts`, `usability.spec.ts`, `user-stories.spec.ts`, or `buyer-flow.spec.ts`; their relevant behavior is intentionally consolidated into this one acceptance journey.

- [x] **Gate E: Preserve and report the successful video**

```powershell
$videos = @(Get-ChildItem .\examples\medusa-agent\e2e\test-results -Filter video.webm -Recurse)
if ($videos.Count -ne 1) {
    throw "Expected exactly one Playwright video, found $($videos.Count)."
}
New-Item -ItemType Directory -Force .\artifacts\routedeck-runtime-boundary | Out-Null
Copy-Item -LiteralPath $videos[0].FullName -Destination .\artifacts\routedeck-runtime-boundary\human-checkout-flow.webm -Force
Get-Item .\artifacts\routedeck-runtime-boundary\human-checkout-flow.webm | Select-Object FullName, Length, LastWriteTime
```

Expected: the stable `.webm` exists and is non-empty. The final handoff links the exact absolute video path and reports the runtime location, startup command, smoke URLs, Playwright command, and outcome.

- [x] **Gate F: Stop the stack without deleting volumes**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\demo-stack.ps1 -Action Down
```

Expected: scoped services stop and protected volumes remain. A protected demo reset or consolidated `release-verify.ps1 -ResetProtectedDemo` remains outside this plan and requires separate explicit approval.

---

## Clean-Break Deletion Checklist

- `examples/medusa-agent/backend/medusa_agent/runtime_factory.py`
- `examples/medusa-agent/backend/medusa_agent/agent_driver.py`
- `examples/medusa-agent/backend/medusa_agent/api/entry.py`
- `examples/medusa-agent/backend/medusa_agent/entry_conversation.py`
- `examples/medusa-agent/frontend/src/app/conversationEntryClient.ts`
- `routedeck_fastapi/conversation_dependencies.py`
- old `routedeck_fastapi/conversation.py` after its route moves
- `packages/react/src/conversation/state.ts`
- `packages/react/src/conversation/transitions.ts`
- public exports for `MedusaRuntime`, `MedusaLangGraphAgentDriver`, `MedusaSessionProjector`, `project_medusa_session`, `MedusaEntryDependencies`, `create_medusa_entry_router`, `RouteDeckConversationDependencies`, `create_routedeck_conversation_router`, and the old multi-argument router builders

No deleted symbol receives an alias, forwarding module, deprecated endpoint, or compatibility response.

## Final Acceptance Matrix

| Gate | Required proof |
| --- | --- |
| Runtime ownership | One framework-built runner supplies navigation, operations, conversation, private forms/events, and derived FastAPI dependencies. |
| Product boundary | Medusa production code supplies declarations, bindings, callbacks, graphs, prompts/models, market facts, commerce adapters, readiness, and UI only. |
| Assistant initiation | Generic typed endpoint streams and persists an assistant-only turn; exact replay works; no empty/synthetic user message exists. |
| User chat | Incremental SSE, serial tools, review, interruption, retry/resync, and durable replay remain unchanged. |
| React | Named presentation actions replace generic transitions while observable RouteDeck state remains canonical. |
| Hotspots | All six files are split by the named responsibilities without parallel public APIs or behavior drift. |
| Boundaries | Schema-3 executable report passes with zero violations and can no longer bless product-owned generic runtime assembly. |
| Surface story | Real RouteDeck-controlled UI dispatches against real Store-backed state. |
| Hybrid story | Agent and surface actions converge on the same supervised runner and durable session. |
| Buyer flow | One live-model journey mixes casual chat, direct surfaces, and hybrid state convergence through real Medusa checkout and confirmation on local Windows. |
| Video evidence | The successful buyer flow is retained at `artifacts/routedeck-runtime-boundary/human-checkout-flow.webm` and linked in the handoff. |

## Plan Self-Review Result

- Spec coverage: all ten required deliverable sections are mapped to exactly five execution slices; internal work packages are not independent review or test boundaries.
- Path review: every existing path was verified against the current tree; every new path is declared in the final layout and the work package that creates it.
- Type review: runtime services precede adapter construction; graph factories consume services; FastAPI consumes the final runtime; typed triggers are identical across Core, LangGraph, FastAPI, and TypeScript.
- Ownership review: no final product file constructs a generic runner, navigation runner, dependency bundle, conversation driver, codec, store, projector, notifier, or ID generator.
- Clean-break review: all five mandated product entry/runtime files plus obsolete generic dependency/React modules are deleted without aliases.
- Failure review: replay, request-ID collision, concurrency, cancellation, interruption persistence, outcome unknown, builder cleanup, and missing credentials all have explicit behavior.
- Test-scope review: no pre-change baselines or per-file test loops remain; each slice has one targeted gate, the all-up regression runs once, and one live human-like checkout produces the required video.
- Non-goal review: no checkout-feature split, UI redesign, alternative model/provider, fake commerce source, deployment, protected reset, or Git operation is included.
