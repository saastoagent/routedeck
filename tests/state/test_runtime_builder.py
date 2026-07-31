from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

from routedeck_core.app import (
    Application,
    FeatureBindings,
    Feature,
    bind_app,
    compile_app,
)
from routedeck_core.contracts.application import Node
from routedeck_core.contracts.events import RouteDeckEvent
from routedeck_core.contracts.navigation import (
    DeepLinkPolicy,
    NodeRef,
    NodeKind,
    Route,
    Transition,
)
from routedeck_core.contracts.operations import (
    OperationOutcome,
    Operation,
    SafetyClass,
)
from routedeck_core.contracts.session import (
    PrivateSessionState,
    PublicSessionState,
    RouteDeckSession,
    SessionSnapshot,
)
from routedeck_core.contracts.surfaces import SurfaceSlots
from routedeck_core.ports.executor import ExecutionContext
from routedeck_core.runtime import (
    RouteDeckRuntime,
    RouteDeckRuntimeLifecycle,
    SessionProvisioningError,
    SessionProvisioningErrorCode,
    build_routedeck_runtime,
)
from routedeck_core.ports import SessionStoreError, SessionStoreErrorCode
from routedeck_core.state.session import create_session, require_current_session
from routedeck_core.validation import RouteDeckValidationError


@dataclass(frozen=True)
class FixedClock:
    current: datetime = datetime(2030, 1, 1, tzinfo=UTC)

    def now(self) -> datetime:
        return self.current


@dataclass
class RecordingNotifier:
    notifications: list[tuple[str, tuple[RouteDeckEvent, ...]]] = field(
        default_factory=list
    )

    async def notify(
        self,
        session_id: str,
        events: Sequence[RouteDeckEvent],
    ) -> None:
        self.notifications.append((session_id, tuple(events)))


@dataclass
class SequentialIds:
    counts: Counter[str] = field(default_factory=Counter)

    def __call__(self, kind: str) -> str:
        self.counts[kind] += 1
        return f"{kind}-{self.counts[kind]}"


class InMemoryTestStore:
    def __init__(self) -> None:
        self.sessions: dict[str, RouteDeckSession] = {}
        self.creation_requests: dict[str, tuple[str, str]] = {}
        self.load_calls: list[str] = []

    async def create(self, initial: RouteDeckSession) -> SessionSnapshot:
        self.sessions[initial.session_id] = initial
        return SessionSnapshot(state=initial)

    async def create_for_request(
        self,
        initial: RouteDeckSession,
        request_id: str,
        request_fingerprint: str,
    ) -> SessionSnapshot:
        existing = self.creation_requests.get(request_id)
        if existing is not None:
            fingerprint, session_id = existing
            if fingerprint != request_fingerprint:
                raise SessionStoreError(SessionStoreErrorCode.REQUEST_ID_REUSED)
            return await self.load(session_id)
        snapshot = await self.create(initial)
        self.creation_requests[request_id] = (
            request_fingerprint,
            initial.session_id,
        )
        return snapshot

    async def load(self, session_id: str) -> SessionSnapshot:
        self.load_calls.append(session_id)
        return SessionSnapshot(state=self.sessions[session_id])


class TestSensitiveCodec:
    def encrypt(self, value: bytes) -> bytes:
        return b"test:" + value

    def decrypt(self, value: bytes) -> bytes:
        if not value.startswith(b"test:"):
            raise ValueError("test ciphertext is invalid")
        return value.removeprefix(b"test:")


@dataclass
class RecordingLifecycle(RouteDeckRuntimeLifecycle):
    close_calls: int = 0

    async def close(self) -> None:
        self.close_calls += 1


async def _unused_handler(
    arguments: object,
    context: ExecutionContext,
) -> OperationOutcome:
    del arguments, context
    raise AssertionError("runtime builder test handler must not execute")


def _bound_test_app():
    operation = Operation(
        id="test.refresh",
        title="Refresh test state",
        description="Refresh the runtime-builder test state.",
        safety_class=SafetyClass.READ_EXTERNAL,
        outcomes=("refreshed",),
    )
    node = Node(
        id="test.home",
        title="Runtime test home",
        kind=NodeKind.SECTION,
        route=Route(template="/", deep_link_policy=DeepLinkPolicy.SHAREABLE),
        operations=(operation,),
        outgoing=(
            Transition(
                operation=operation.ref,
                outcome="refreshed",
                target=NodeRef(id="test.home"),
            ),
        ),
        surfaces=SurfaceSlots(active=None),
    )
    compiled = compile_app(
        Application(
            name="runtime-builder-test",
            entry_node=node.ref,
            features=(
                Feature(
                    namespace="test",
                    nodes=(node,),
                ),
            ),
        )
    )
    return bind_app(
        compiled,
        FeatureBindings(
            handlers={operation.ref: _unused_handler},
            providers={},
            guards={},
        ),
    )


def build_test_routedeck_runtime_with_lifecycle() -> tuple[
    RouteDeckRuntime,
    RecordingLifecycle,
]:
    app = _bound_test_app()
    lifecycle = RecordingLifecycle()
    store = InMemoryTestStore()

    def make_session(compiled_app, session_id: str) -> RouteDeckSession:
        return create_session(
            app=compiled_app,
            session_id=session_id,
            private_state=PrivateSessionState(),
        )

    async def initialize_session(_services, snapshot: SessionSnapshot) -> SessionSnapshot:
        return snapshot

    runtime = build_routedeck_runtime(
        app=app,
        store=store,  # type: ignore[arg-type]
        private_form_codec=TestSensitiveCodec(),
        session_factory=make_session,
        session_initializer=initialize_session,
        public_key_validator_factory=lambda _session: None,
        agent_driver_factory=None,
        lifecycle=lifecycle,
        clock=FixedClock(),
        notifier=RecordingNotifier(),
        id_factory=SequentialIds(),
        review_ttl=timedelta(minutes=5),
        resume_capability_ttl=timedelta(hours=1),
    )
    return runtime, lifecycle


def build_test_routedeck_runtime() -> RouteDeckRuntime:
    runtime, _lifecycle = build_test_routedeck_runtime_with_lifecycle()
    return runtime


def test_runtime_builder_reuses_one_runner_for_navigation() -> None:
    runtime = build_test_routedeck_runtime()

    assert runtime.services.navigation.operation_runner is runtime.services.runner
    assert runtime.services.projector.app is runtime.services.app.app


@pytest.mark.asyncio
async def test_runtime_close_uses_the_explicit_lifecycle_once() -> None:
    runtime, lifecycle = build_test_routedeck_runtime_with_lifecycle()

    await runtime.close()

    assert lifecycle.close_calls == 1


@pytest.mark.asyncio
async def test_runtime_provisions_and_replays_the_current_session_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = build_test_routedeck_runtime()
    store = runtime.services.store
    assert isinstance(store, InMemoryTestStore)
    calls: list[tuple[str, str]] = []

    async def make_session(compiled_app, session_id: str) -> RouteDeckSession:
        assert compiled_app is runtime.services.app.app
        calls.append(("factory", session_id))
        return create_session(
            app=compiled_app,
            session_id=session_id,
            private_state=PrivateSessionState(),
        )

    async def initialize_session(
        services,
        snapshot: SessionSnapshot,
    ) -> SessionSnapshot:
        assert services is runtime.services
        calls.append(("initializer", snapshot.session_id))
        return snapshot

    async def ensure_entry(snapshot: SessionSnapshot):
        calls.append(("entry", snapshot.session_id))
        if snapshot.session_version == 1:
            store.sessions[snapshot.session_id] = snapshot.state.model_copy(
                update={
                    "session_version": 2,
                    "projection_version": 2,
                }
            )
        return None

    object.__setattr__(runtime, "session_factory", make_session)
    object.__setattr__(runtime, "session_initializer", initialize_session)
    monkeypatch.setattr(
        runtime.conversation_runs,
        "ensure_declared_entry_run",
        ensure_entry,
    )

    created = await runtime.provision_session(
        session_id="provisioned-session",
        request_id="create-request",
    )
    replayed = await runtime.provision_session(
        session_id="discarded-replay-session",
        request_id="create-request",
    )

    assert created.session_id == "provisioned-session"
    assert created.session_version == 2
    assert replayed == created
    assert store.creation_requests == {
        "create-request": (
            hashlib.sha256(b"routedeck.session-creation.v1").hexdigest(),
            "provisioned-session",
        )
    }
    assert calls == [
        ("factory", "provisioned-session"),
        ("initializer", "provisioned-session"),
        ("entry", "provisioned-session"),
        ("factory", "discarded-replay-session"),
        ("initializer", "provisioned-session"),
        ("entry", "provisioned-session"),
    ]
    assert store.load_calls == [
        "provisioned-session",
        "provisioned-session",
        "provisioned-session",
    ]


@pytest.mark.asyncio
async def test_runtime_provisioning_preserves_request_collision_semantics() -> None:
    runtime = build_test_routedeck_runtime()
    store = runtime.services.store
    assert isinstance(store, InMemoryTestStore)
    store.creation_requests["create-request"] = (
        "different-fingerprint",
        "existing-session",
    )

    with pytest.raises(SessionStoreError) as raised:
        await runtime.provision_session(
            session_id="new-session",
            request_id="create-request",
        )

    assert raised.value.code is SessionStoreErrorCode.REQUEST_ID_REUSED


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_result", ["identity", "version"])
async def test_runtime_rejects_invalid_session_initializer_result(
    invalid_result: str,
) -> None:
    runtime = build_test_routedeck_runtime()

    async def invalid_initializer(
        _services,
        snapshot: SessionSnapshot,
    ) -> SessionSnapshot:
        update = (
            {"session_id": "different-session"}
            if invalid_result == "identity"
            else {
                "session_version": snapshot.session_version - 1,
                "projection_version": snapshot.projection_version - 1,
            }
        )
        return SessionSnapshot.model_construct(
            state=snapshot.state.model_copy(update=update)
        )

    object.__setattr__(runtime, "session_initializer", invalid_initializer)

    with pytest.raises(SessionProvisioningError) as raised:
        await runtime.provision_session(
            session_id="invalid-initializer-session",
            request_id=f"invalid-{invalid_result}",
        )

    assert (
        raised.value.code
        is SessionProvisioningErrorCode.SESSION_INITIALIZER_INVALID
    )


def test_session_creation_uses_defaults_or_the_exact_supplied_public_state() -> None:
    app = _bound_test_app().app
    private_state = PrivateSessionState()
    defaulted = create_session(
        app=app,
        session_id="default-session",
        private_state=private_state,
    )
    supplied_public_state = PublicSessionState(status_message="Ready")
    supplied = create_session(
        app=app,
        session_id="supplied-session",
        private_state=private_state,
        public_state=supplied_public_state,
    )

    assert defaulted.public_state == PublicSessionState()
    assert supplied.public_state is supplied_public_state
    require_current_session(app, defaulted)


@pytest.mark.parametrize(
    "field,value",
    (
        ("schema_version", 3),
        ("navgraph_version", "different-navgraph"),
    ),
)
def test_current_session_validation_rejects_each_incompatible_identity(
    field: str,
    value: object,
) -> None:
    app = _bound_test_app().app
    session = create_session(
        app=app,
        session_id="incompatible-session",
        private_state=PrivateSessionState(),
    ).model_copy(update={field: value})

    with pytest.raises(RouteDeckValidationError, match="session_upgrade_required"):
        require_current_session(app, session)
