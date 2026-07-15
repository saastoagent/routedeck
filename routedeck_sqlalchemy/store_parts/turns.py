from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.orm import Session

from routedeck_core.contracts.events import RouteDeckEvent
from routedeck_core.contracts.session import RouteDeckSession
from routedeck_core.state.leases import TurnClaim, TurnLease

from ..sessions import SessionRepository
from ..turns import TurnRepository
from .lifecycle import _StoreLifecycle


class _TurnTransactions:
    def __init__(
        self,
        *,
        lifecycle: _StoreLifecycle,
        sessions: SessionRepository,
        turns: TurnRepository,
    ) -> None:
        self._lifecycle = lifecycle
        self._sessions = sessions
        self._turns = turns

    async def acquire_turn(self, claim: TurnClaim) -> TurnLease:
        return await self._lifecycle.write(
            lambda database, now: self._turns.acquire(
                database,
                claim,
                now=now,
                application_lease=self._lifecycle.runtime.application_lease,
            )
        )

    async def start_turn(
        self,
        claim: TurnClaim,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
    ) -> TurnLease:
        def start(database: Session, now: datetime) -> TurnLease:
            lease = self._turns.acquire(
                database,
                claim,
                now=now,
                application_lease=self._lifecycle.runtime.application_lease,
            )
            self._sessions.commit(
                database,
                session_id=claim.session_id,
                expected_session_version=claim.expected_session_version,
                next_state=next_state,
                events=events,
                now=now,
                lease=self._lifecycle.runtime.application_lease,
            )
            return lease

        return await self._lifecycle.write(start)

    async def claim_child_attempt(
        self,
        lease: TurnLease,
        request_id: str,
        request_fingerprint: str,
    ) -> None:
        await self._lifecycle.write(
            lambda database, now: self._turns.claim_child(
                database,
                lease,
                request_id=request_id,
                request_fingerprint=request_fingerprint,
                now=now,
                application_lease=self._lifecycle.runtime.application_lease,
            )
        )

    async def release_child_attempt(
        self,
        lease: TurnLease,
        request_id: str,
    ) -> None:
        await self._lifecycle.write(
            lambda database, _now: self._turns.release_child(
                database,
                lease,
                request_id=request_id,
                application_lease=self._lifecycle.runtime.application_lease,
            )
        )
