from __future__ import annotations

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
from routedeck_core.contracts.session import RouteDeckSession, SessionSnapshot
from routedeck_core.contracts.surfaces import SurfaceSlots
from routedeck_core.ports.executor import ExecutionContext
from routedeck_core.runtime import (
    RouteDeckRuntime,
    RouteDeckRuntimeLifecycle,
    build_routedeck_runtime,
)
from routedeck_core.state.session import create_session


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

    async def create(self, initial: RouteDeckSession) -> SessionSnapshot:
        self.sessions[initial.session_id] = initial
        return SessionSnapshot(state=initial)

    async def load(self, session_id: str) -> SessionSnapshot:
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
        return create_session(app=compiled_app, session_id=session_id)

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
        default_session_id="runtime-test-session",
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
