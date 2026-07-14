from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from typing import Protocol, runtime_checkable

from ..contracts.conversation import FinalizedConversationTurn
from ..contracts.events import RouteDeckEvent, EventPage
from ..contracts.failures import RouteDeckFailure
from ..contracts.mutations import MutationCommit, MutationRecord
from ..contracts.session import (
    JournaledExecutionResult,
    PendingReview,
    RouteDeckSession,
    SessionSnapshot,
    StoredOperationAttempt,
)
from ..state.leases import ExecutionClaim, TurnClaim, TurnLease


class SessionStoreErrorCode(StrEnum):
    SESSION_ALREADY_EXISTS = "session_already_exists"
    SESSION_NOT_FOUND = "session_not_found"
    SESSION_EXPIRED = "session_expired"
    SESSION_UPGRADE_REQUIRED = "session_upgrade_required"
    VERSION_CONFLICT = "version_conflict"
    REQUEST_ID_REUSED = "request_id_reused"
    OPERATION_IN_PROGRESS = "operation_in_progress"
    LEASE_MISMATCH = "lease_mismatch"
    EXECUTION_ALREADY_CLAIMED = "execution_already_claimed"
    REVIEW_ALREADY_RESOLVED = "review_already_resolved"
    RESULT_MISMATCH = "result_mismatch"
    PERSISTENCE_FAILURE = "persistence_failure"


class SessionStoreError(RuntimeError):
    def __init__(self, code: SessionStoreErrorCode) -> None:
        super().__init__(code.value)
        self.code = code


@runtime_checkable
class RouteDeckSessionStore(Protocol):
    async def create(self, initial: RouteDeckSession) -> SessionSnapshot: ...

    async def create_for_request(
        self,
        initial: RouteDeckSession,
        request_id: str,
        request_fingerprint: str,
    ) -> SessionSnapshot: ...

    async def load(self, session_id: str) -> SessionSnapshot: ...

    async def find_attempt(
        self,
        session_id: str,
        request_id: str,
    ) -> StoredOperationAttempt | None: ...

    async def find_review(
        self,
        session_id: str,
        review_id: str,
    ) -> PendingReview | None: ...

    async def find_mutation(
        self,
        session_id: str,
        request_id: str,
    ) -> MutationRecord | None: ...

    async def acquire_turn(self, claim: TurnClaim) -> TurnLease: ...

    async def start_turn(
        self,
        claim: TurnClaim,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
    ) -> TurnLease: ...

    async def claim_child_attempt(
        self,
        lease: TurnLease,
        request_id: str,
        request_fingerprint: str,
    ) -> None: ...

    async def release_child_attempt(
        self,
        lease: TurnLease,
        request_id: str,
    ) -> None: ...

    async def stage_review(
        self,
        lease: TurnLease,
        expected_session_version: int,
        record: StoredOperationAttempt,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
        parent_mutation: MutationCommit | None = None,
    ) -> SessionSnapshot: ...

    async def claim_execution(
        self,
        lease: TurnLease,
        record: StoredOperationAttempt,
    ) -> ExecutionClaim: ...

    async def recover_execution_claim(
        self,
        lease: TurnLease,
        attempt_id: str,
    ) -> ExecutionClaim: ...

    async def record_execution_result(
        self,
        claim: ExecutionClaim,
        result: JournaledExecutionResult,
        record: StoredOperationAttempt,
    ) -> None: ...

    async def record_execution_started(
        self,
        claim: ExecutionClaim,
        record: StoredOperationAttempt,
    ) -> None: ...

    async def commit_state(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
        mutation: MutationCommit,
    ) -> SessionSnapshot: ...

    async def finalize_turn(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        turns: Sequence[FinalizedConversationTurn],
        events: Sequence[RouteDeckEvent],
        mutation: MutationCommit,
    ) -> SessionSnapshot: ...

    async def interrupt_turn(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        failure: RouteDeckFailure,
        events: Sequence[RouteDeckEvent],
        mutation: MutationCommit,
    ) -> SessionSnapshot: ...

    async def commit_attempt(
        self,
        claim: ExecutionClaim,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
        record: StoredOperationAttempt,
    ) -> SessionSnapshot:
        """Atomically commit state, attempt, events, and requested completion.

        A successful journaled result can carry
        ``SessionEffects.complete_session``. Implementations must apply that
        retention transition in this same commit; it is never a follow-up
        best-effort store call.
        """

        ...

    async def commit_supervision(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
        record: StoredOperationAttempt,
    ) -> SessionSnapshot: ...

    async def mark_external_outcome_unknown(
        self,
        claim: ExecutionClaim,
        expected_session_version: int,
        record: StoredOperationAttempt,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
    ) -> SessionSnapshot: ...

    async def release_turn(self, lease: TurnLease) -> None: ...

    async def events_after(
        self,
        session_id: str,
        cursor: int,
        limit: int,
    ) -> EventPage: ...

    async def load_private_blob(
        self,
        session_id: str,
        form_id: str,
    ) -> bytes | None: ...

    async def save_private_blob(
        self,
        lease: TurnLease,
        expected_session_version: int,
        form_id: str,
        encrypted_value: bytes,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
        mutation: MutationCommit,
    ) -> SessionSnapshot: ...


__all__ = [
    "RouteDeckSessionStore",
    "SessionStoreError",
    "SessionStoreErrorCode",
]
