from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.orm import Session

from routedeck_core.contracts.events import RouteDeckEvent
from routedeck_core.contracts.mutations import MutationCommit
from routedeck_core.contracts.session import RouteDeckSession, SessionSnapshot
from routedeck_core.ports.codec import SensitiveCodec
from routedeck_core.state.leases import TurnLease

from ..sessions import SessionRepository
from ..turns import TurnRepository
from .lifecycle import _StoreLifecycle


class _PrivateFormTransactions:
    def __init__(
        self,
        *,
        lifecycle: _StoreLifecycle,
        codec: SensitiveCodec,
        sessions: SessionRepository,
        turns: TurnRepository,
    ) -> None:
        self._lifecycle = lifecycle
        self._codec = codec
        self._sessions = sessions
        self._turns = turns

    async def load_private_blob(
        self,
        session_id: str,
        form_id: str,
    ) -> bytes | None:
        return await self._lifecycle.read(
            lambda database, now: self._sessions.load_private_blob(
                database,
                session_id=session_id,
                form_id=form_id,
                now=now,
            )
        )

    async def save_private_blob(
        self,
        lease: TurnLease,
        expected_session_version: int,
        form_id: str,
        encrypted_value: bytes,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
        mutation: MutationCommit,
    ) -> SessionSnapshot:
        if not form_id:
            raise ValueError("form_id is required")
        self._codec.decrypt(encrypted_value)

        def save(database: Session, now: datetime) -> SessionSnapshot:
            self._turns.require_lease(
                database,
                lease,
                application_lease=self._lifecycle.runtime.application_lease,
            )
            snapshot = self._sessions.commit(
                database,
                session_id=lease.session_id,
                expected_session_version=expected_session_version,
                next_state=next_state,
                events=events,
                now=now,
                lease=self._lifecycle.runtime.application_lease,
            )
            self._sessions.put_private_blob(
                database,
                session_id=lease.session_id,
                form_id=form_id,
                encrypted_value=encrypted_value,
                now=now,
            )
            self._turns.record_mutation(
                database,
                lease,
                mutation,
                snapshot,
                now=now,
                application_lease=self._lifecycle.runtime.application_lease,
            )
            return snapshot

        return await self._lifecycle.write(save)
