from __future__ import annotations

from collections.abc import Sequence

from routedeck_core.contracts.events import RouteDeckEvent
from routedeck_core.contracts.mutations import MutationCommit
from routedeck_core.contracts.session import (
    JournaledExecutionResult,
    RouteDeckSession,
    SessionSnapshot,
    StoredOperationAttempt,
)
from routedeck_core.state.leases import ExecutionClaim, TurnLease

from ..commits import SqlAlchemyCommitCoordinator
from ..operations import OperationRepository
from .lifecycle import _StoreLifecycle


class _SupervisionTransactions:
    def __init__(
        self,
        *,
        lifecycle: _StoreLifecycle,
        operations: OperationRepository,
        commits: SqlAlchemyCommitCoordinator,
    ) -> None:
        self._lifecycle = lifecycle
        self._operations = operations
        self._commits = commits

    async def stage_review(
        self,
        lease: TurnLease,
        expected_session_version: int,
        record: StoredOperationAttempt,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
        parent_mutation: MutationCommit | None = None,
    ) -> SessionSnapshot:
        if record.review is None:
            raise ValueError("stage_review requires a review record")
        return await self._commits.with_lease(
            lease,
            expected_session_version,
            next_state,
            events,
            record=record,
            journal_phase="review_staged",
            mutation=parent_mutation,
        )

    async def claim_execution(
        self,
        lease: TurnLease,
        record: StoredOperationAttempt,
    ) -> ExecutionClaim:
        return await self._lifecycle.write(
            lambda database, now: self._operations.claim_execution(
                database,
                lease,
                record,
                now=now,
                application_lease=self._lifecycle.runtime.application_lease,
            )
        )

    async def recover_execution_claim(
        self,
        lease: TurnLease,
        attempt_id: str,
    ) -> ExecutionClaim:
        return await self._lifecycle.write(
            lambda database, now: self._operations.recover_execution_claim(
                database,
                lease,
                attempt_id,
                now=now,
                application_lease=self._lifecycle.runtime.application_lease,
            )
        )

    async def record_execution_result(
        self,
        claim: ExecutionClaim,
        result: JournaledExecutionResult,
        record: StoredOperationAttempt,
    ) -> None:
        await self._lifecycle.write(
            lambda database, now: self._operations.record_execution_result(
                database,
                claim,
                result,
                record,
                now=now,
                application_lease=self._lifecycle.runtime.application_lease,
            )
        )

    async def record_execution_started(
        self,
        claim: ExecutionClaim,
        record: StoredOperationAttempt,
    ) -> None:
        await self._lifecycle.write(
            lambda database, now: self._operations.record_execution_started(
                database,
                claim,
                record,
                now=now,
                application_lease=self._lifecycle.runtime.application_lease,
            )
        )
