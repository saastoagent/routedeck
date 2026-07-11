from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from ..contracts.conversation import FinalizedConversationTurn
from ..contracts.events import CanonicalRouteDeckEvent, EventPage
from ..contracts.failures import RouteDeckFailure
from ..contracts.session import (
    AttemptTerminalState,
    JournaledExecutionResult,
    OperationAttempt,
    PendingReview,
    RouteDeckSession,
    SessionSnapshot,
)
from ..state.leases import ExecutionClaim, TurnClaim, TurnLease


@runtime_checkable
class RouteDeckSessionStore(Protocol):
    async def create(self, initial: RouteDeckSession) -> SessionSnapshot: ...

    async def load(self, session_id: str) -> SessionSnapshot: ...

    async def find_attempt(
        self,
        session_id: str,
        request_id: str,
    ) -> OperationAttempt | None: ...

    async def acquire_turn(self, claim: TurnClaim) -> TurnLease: ...

    async def stage_review(
        self,
        lease: TurnLease,
        review: PendingReview,
    ) -> SessionSnapshot: ...

    async def claim_execution(
        self,
        lease: TurnLease,
        attempt: OperationAttempt,
    ) -> ExecutionClaim: ...

    async def record_execution_result(
        self,
        claim: ExecutionClaim,
        result: JournaledExecutionResult,
    ) -> None: ...

    async def commit_state(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[CanonicalRouteDeckEvent],
    ) -> SessionSnapshot: ...

    async def finalize_turn(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        turns: Sequence[FinalizedConversationTurn],
        events: Sequence[CanonicalRouteDeckEvent],
    ) -> SessionSnapshot: ...

    async def interrupt_turn(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        failure: RouteDeckFailure,
        events: Sequence[CanonicalRouteDeckEvent],
    ) -> SessionSnapshot: ...

    async def commit_attempt(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[CanonicalRouteDeckEvent],
        terminal: AttemptTerminalState,
    ) -> SessionSnapshot: ...

    async def mark_external_outcome_unknown(
        self,
        claim: ExecutionClaim,
        failure: RouteDeckFailure,
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
    ) -> SessionSnapshot: ...


__all__ = ["RouteDeckSessionStore"]
