from __future__ import annotations

from routedeck_core.contracts.mutations import MutationRecord
from routedeck_core.contracts.session import (
    PendingReview,
    RouteDeckSession,
    SessionSnapshot,
    StoredOperationAttempt,
)

from ..operations import OperationRepository
from ..sessions import SessionRepository
from ..turns import TurnRepository
from .lifecycle import _StoreLifecycle


class _SessionTransactions:
    def __init__(
        self,
        *,
        lifecycle: _StoreLifecycle,
        sessions: SessionRepository,
        operations: OperationRepository,
        turns: TurnRepository,
    ) -> None:
        self._lifecycle = lifecycle
        self._sessions = sessions
        self._operations = operations
        self._turns = turns

    async def create(self, initial: RouteDeckSession) -> SessionSnapshot:
        return await self._lifecycle.write(
            lambda database, now: self._sessions.insert(
                database,
                initial,
                now=now,
                lease=self._lifecycle.runtime.application_lease,
            )
        )

    async def load(self, session_id: str) -> SessionSnapshot:
        return await self._lifecycle.read(
            lambda database, now: self._sessions.load(
                database,
                session_id,
                now=now,
            )
        )

    async def create_for_request(
        self,
        initial: RouteDeckSession,
        request_id: str,
        request_fingerprint: str,
    ) -> SessionSnapshot:
        return await self._lifecycle.write(
            lambda database, now: self._sessions.create_for_request(
                database,
                initial,
                request_id=request_id,
                request_fingerprint=request_fingerprint,
                now=now,
                lease=self._lifecycle.runtime.application_lease,
            )
        )

    async def find_attempt(
        self,
        session_id: str,
        request_id: str,
    ) -> StoredOperationAttempt | None:
        return await self._lifecycle.read(
            lambda database, now: self._operations.find_attempt(
                database,
                session_id=session_id,
                request_id=request_id,
                now=now,
            )
        )

    async def find_review(
        self,
        session_id: str,
        review_id: str,
    ) -> PendingReview | None:
        return await self._lifecycle.read(
            lambda database, now: self._operations.find_review(
                database,
                session_id=session_id,
                review_id=review_id,
                now=now,
            )
        )

    async def find_mutation(
        self,
        session_id: str,
        request_id: str,
    ) -> MutationRecord | None:
        return await self._lifecycle.read(
            lambda database, now: self._turns.find_mutation(
                database,
                session_id=session_id,
                request_id=request_id,
                now=now,
            )
        )
