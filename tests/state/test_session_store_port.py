from __future__ import annotations

import inspect
from collections.abc import Sequence
from typing import get_type_hints

import pytest

from routedeck_core.contracts.conversation import FinalizedConversationTurn
from routedeck_core.contracts.events import EventPage, RouteDeckEvent
from routedeck_core.contracts.failures import RouteDeckFailure
from routedeck_core.contracts.mutations import MutationCommit, MutationRecord
from routedeck_core.contracts.session import (
    JournaledExecutionResult,
    PendingReview,
    RouteDeckSession,
    SessionSnapshot,
    StoredOperationAttempt,
)
from routedeck_core.ports.session_store import RouteDeckSessionStore
from routedeck_core.state.leases import ExecutionClaim, TurnClaim, TurnLease
from routedeck_testing.conformance import assert_session_store_conforms


EXPECTED_PARAMETERS = {
    "create": ("self", "initial"),
    "create_for_request": (
        "self",
        "initial",
        "request_id",
        "request_fingerprint",
    ),
    "load": ("self", "session_id"),
    "find_attempt": ("self", "session_id", "request_id"),
    "find_review": ("self", "session_id", "review_id"),
    "find_mutation": ("self", "session_id", "request_id"),
    "acquire_turn": ("self", "claim"),
    "claim_child_attempt": (
        "self",
        "lease",
        "request_id",
        "request_fingerprint",
    ),
    "release_child_attempt": ("self", "lease", "request_id"),
    "stage_review": (
        "self",
        "lease",
        "expected_session_version",
        "record",
        "next_state",
        "events",
        "parent_mutation",
    ),
    "claim_execution": ("self", "lease", "record"),
    "recover_execution_claim": ("self", "lease", "attempt_id"),
    "record_execution_started": ("self", "claim", "record"),
    "record_execution_result": ("self", "claim", "result", "record"),
    "commit_state": (
        "self",
        "lease",
        "expected_session_version",
        "next_state",
        "events",
        "mutation",
    ),
    "finalize_turn": (
        "self",
        "lease",
        "expected_session_version",
        "next_state",
        "turns",
        "events",
        "mutation",
    ),
    "interrupt_turn": (
        "self",
        "lease",
        "expected_session_version",
        "next_state",
        "failure",
        "events",
        "mutation",
    ),
    "commit_attempt": (
        "self",
        "claim",
        "expected_session_version",
        "next_state",
        "events",
        "record",
    ),
    "commit_supervision": (
        "self",
        "lease",
        "expected_session_version",
        "next_state",
        "events",
        "record",
    ),
    "mark_external_outcome_unknown": (
        "self",
        "claim",
        "expected_session_version",
        "record",
        "next_state",
        "events",
    ),
    "release_turn": ("self", "lease"),
    "events_after": ("self", "session_id", "cursor", "limit"),
    "load_private_blob": ("self", "session_id", "form_id"),
    "save_private_blob": (
        "self",
        "lease",
        "expected_session_version",
        "form_id",
        "encrypted_value",
        "next_state",
        "events",
        "mutation",
    ),
}

EXPECTED_RETURNS = {
    "create": SessionSnapshot,
    "create_for_request": SessionSnapshot,
    "load": SessionSnapshot,
    "find_attempt": StoredOperationAttempt | None,
    "find_review": PendingReview | None,
    "find_mutation": MutationRecord | None,
    "acquire_turn": TurnLease,
    "claim_child_attempt": type(None),
    "release_child_attempt": type(None),
    "stage_review": SessionSnapshot,
    "claim_execution": ExecutionClaim,
    "recover_execution_claim": ExecutionClaim,
    "record_execution_started": type(None),
    "record_execution_result": type(None),
    "commit_state": SessionSnapshot,
    "finalize_turn": SessionSnapshot,
    "interrupt_turn": SessionSnapshot,
    "commit_attempt": SessionSnapshot,
    "commit_supervision": SessionSnapshot,
    "mark_external_outcome_unknown": SessionSnapshot,
    "release_turn": type(None),
    "events_after": EventPage,
    "load_private_blob": bytes | None,
    "save_private_blob": SessionSnapshot,
}


class CompleteStoreDouble:
    async def create(self, initial: RouteDeckSession) -> SessionSnapshot:
        raise AssertionError("conformance must not execute store methods")

    async def create_for_request(
        self,
        initial: RouteDeckSession,
        request_id: str,
        request_fingerprint: str,
    ) -> SessionSnapshot:
        raise AssertionError("conformance must not execute store methods")

    async def load(self, session_id: str) -> SessionSnapshot:
        raise AssertionError("conformance must not execute store methods")

    async def find_attempt(
        self, session_id: str, request_id: str
    ) -> StoredOperationAttempt | None:
        raise AssertionError("conformance must not execute store methods")

    async def find_review(
        self, session_id: str, review_id: str
    ) -> PendingReview | None:
        raise AssertionError("conformance must not execute store methods")

    async def find_mutation(
        self,
        session_id: str,
        request_id: str,
    ) -> MutationRecord | None:
        raise AssertionError("conformance must not execute store methods")

    async def acquire_turn(self, claim: TurnClaim) -> TurnLease:
        raise AssertionError("conformance must not execute store methods")

    async def claim_child_attempt(
        self,
        lease: TurnLease,
        request_id: str,
        request_fingerprint: str,
    ) -> None:
        raise AssertionError("conformance must not execute store methods")

    async def release_child_attempt(self, lease: TurnLease, request_id: str) -> None:
        raise AssertionError("conformance must not execute store methods")

    async def stage_review(
        self,
        lease: TurnLease,
        expected_session_version: int,
        record: StoredOperationAttempt,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
        parent_mutation: MutationCommit | None = None,
    ) -> SessionSnapshot:
        raise AssertionError("conformance must not execute store methods")

    async def claim_execution(
        self, lease: TurnLease, record: StoredOperationAttempt
    ) -> ExecutionClaim:
        raise AssertionError("conformance must not execute store methods")

    async def recover_execution_claim(
        self, lease: TurnLease, attempt_id: str
    ) -> ExecutionClaim:
        raise AssertionError("conformance must not execute store methods")

    async def record_execution_started(
        self, claim: ExecutionClaim, record: StoredOperationAttempt
    ) -> None:
        raise AssertionError("conformance must not execute store methods")

    async def record_execution_result(
        self,
        claim: ExecutionClaim,
        result: JournaledExecutionResult,
        record: StoredOperationAttempt,
    ) -> None:
        raise AssertionError("conformance must not execute store methods")

    async def commit_state(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
        mutation: MutationCommit,
    ) -> SessionSnapshot:
        raise AssertionError("conformance must not execute store methods")

    async def finalize_turn(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        turns: Sequence[FinalizedConversationTurn],
        events: Sequence[RouteDeckEvent],
        mutation: MutationCommit,
    ) -> SessionSnapshot:
        raise AssertionError("conformance must not execute store methods")

    async def interrupt_turn(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        failure: RouteDeckFailure,
        events: Sequence[RouteDeckEvent],
        mutation: MutationCommit,
    ) -> SessionSnapshot:
        raise AssertionError("conformance must not execute store methods")

    async def commit_attempt(
        self,
        claim: ExecutionClaim,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
        record: StoredOperationAttempt,
    ) -> SessionSnapshot:
        raise AssertionError("conformance must not execute store methods")

    async def commit_supervision(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
        record: StoredOperationAttempt,
    ) -> SessionSnapshot:
        raise AssertionError("conformance must not execute store methods")

    async def mark_external_outcome_unknown(
        self,
        claim: ExecutionClaim,
        expected_session_version: int,
        record: StoredOperationAttempt,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
    ) -> SessionSnapshot:
        raise AssertionError("conformance must not execute store methods")

    async def release_turn(self, lease: TurnLease) -> None:
        raise AssertionError("conformance must not execute store methods")

    async def events_after(self, session_id: str, cursor: int, limit: int) -> EventPage:
        raise AssertionError("conformance must not execute store methods")

    async def load_private_blob(self, session_id: str, form_id: str) -> bytes | None:
        raise AssertionError("conformance must not execute store methods")

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
        raise AssertionError("conformance must not execute store methods")


class SignatureMismatchStoreDouble(CompleteStoreDouble):
    async def load(self) -> SessionSnapshot:  # type: ignore[override]
        raise AssertionError("conformance must not execute store methods")


class KeywordOnlyStoreDouble(CompleteStoreDouble):
    async def load(  # type: ignore[override]
        self,
        *,
        session_id: str,
    ) -> SessionSnapshot:
        raise AssertionError("conformance must not execute store methods")


def test_session_store_port_exposes_exact_typed_transaction_boundaries() -> None:
    assert set(EXPECTED_PARAMETERS) <= set(RouteDeckSessionStore.__dict__)
    for name, expected_parameters in EXPECTED_PARAMETERS.items():
        method = RouteDeckSessionStore.__dict__[name]
        signature = inspect.signature(method)
        hints = get_type_hints(method)

        assert inspect.iscoroutinefunction(method), name
        assert tuple(signature.parameters) == expected_parameters, name
        assert all(
            parameter == "self" or parameter in hints
            for parameter in expected_parameters
        ), name
        assert hints["return"] == EXPECTED_RETURNS[name], name


def test_conformance_accepts_a_complete_store_without_executing_it() -> None:
    assert_session_store_conforms(CompleteStoreDouble())


def test_conformance_fails_loudly_for_an_incomplete_store() -> None:
    with pytest.raises(TypeError):
        assert_session_store_conforms(object())


def test_conformance_rejects_an_incompatible_store_signature() -> None:
    with pytest.raises(TypeError, match="incompatible signatures: load"):
        assert_session_store_conforms(SignatureMismatchStoreDouble())

    with pytest.raises(TypeError, match="incompatible signatures: load"):
        assert_session_store_conforms(KeywordOnlyStoreDouble())
