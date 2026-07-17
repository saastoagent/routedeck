from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import pytest
from cryptography.fernet import Fernet

from routedeck_core.app import (
    Application,
    FeatureBindings,
    Feature,
    bind_app,
    compile_app,
)
from routedeck_core.contracts.application import Node
from routedeck_core.contracts.navigation import DeepLinkPolicy, NodeKind, Route
from routedeck_core.contracts.surfaces import SurfaceSlots
from routedeck_core.runtime_defaults import UtcClock
from routedeck_sqlalchemy import (
    FernetSensitiveCodec,
    SqlAlchemySessionStore,
    open_sqlalchemy_routedeck_runtime,
)
from routedeck_testing.factories import session_factory


@dataclass
class _ClosableOpenedStore:
    close_calls: int = 0

    async def close(self) -> None:
        self.close_calls += 1


def _compiled_test_app(name: str):
    node = Node(
        id="test.home",
        title="Test home",
        kind=NodeKind.SECTION,
        route=Route(
            template="/",
            deep_link_policy=DeepLinkPolicy.SHAREABLE,
        ),
        surfaces=SurfaceSlots(active=None),
    )
    return compile_app(
        Application(
            name=name,
            entry_node=node.ref,
            features=(Feature(namespace="test", nodes=(node,)),),
        )
    )


@pytest.mark.asyncio
async def test_sqlalchemy_store_persists_a_session_with_sqlite(tmp_path) -> None:
    database_path = tmp_path / "routedeck.sqlite"
    store = await SqlAlchemySessionStore.open(
        f"sqlite+pysqlite:///{database_path.as_posix()}",
        instance_id="sqlite-session-smoke",
        codec=FernetSensitiveCodec(Fernet.generate_key()),
        clock=UtcClock(),
    )
    initial = session_factory(session_id="sqlalchemy-session")

    try:
        created = await store.create(initial)
        loaded = await store.load(initial.session_id)
    finally:
        await store.close()

    assert created.state == initial
    assert loaded.state == initial
    assert store.dialect_name == "sqlite"


@pytest.mark.asyncio
@pytest.mark.parametrize("factory_mode", ("raises", "wrong_app"))
async def test_runtime_opener_closes_store_when_application_binding_fails(
    monkeypatch: pytest.MonkeyPatch,
    factory_mode: str,
) -> None:
    opened_store = _ClosableOpenedStore()

    async def fake_open(_cls, *_args, **_kwargs):
        return opened_store

    monkeypatch.setattr(
        SqlAlchemySessionStore,
        "open",
        classmethod(fake_open),
    )
    compiled = _compiled_test_app("runtime-opener-test")
    wrong_bound = bind_app(
        _compiled_test_app("wrong-runtime-opener-test"),
        FeatureBindings(handlers={}, providers={}, guards={}),
    )

    def application_factory(_resources):
        if factory_mode == "raises":
            raise RuntimeError("injected application binding failure")
        return wrong_bound

    expected_error = RuntimeError if factory_mode == "raises" else ValueError
    with pytest.raises(expected_error):
        await open_sqlalchemy_routedeck_runtime(
            compiled_app=compiled,
            application_factory=application_factory,
            session_factory=lambda app, session_id: session_factory(
                app=app,
                session_id=session_id,
            ),
            session_initializer=lambda _services, snapshot: snapshot,
            public_key_validator_factory=lambda _session: None,
            agent_driver_factory=None,
            database_url="sqlite+pysqlite:///:memory:",
            encryption_key=Fernet.generate_key(),
            instance_id="runtime-opener-failure",
            review_ttl=timedelta(minutes=5),
            resume_capability_ttl=timedelta(hours=1),
            default_session_id="runtime-opener-session",
        )

    assert opened_store.close_calls == 1
