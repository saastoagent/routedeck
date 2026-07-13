from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from routedeck_sqlalchemy import (
    FernetSensitiveCodec,
    SqlAlchemySessionStore,
    UtcClock,
)
from routedeck_testing.factories import session_factory


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
