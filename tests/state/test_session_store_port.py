from __future__ import annotations

import inspect
from collections.abc import Sequence
from typing import get_type_hints

import pytest

from routedeck_core.contracts.conversation import FinalizedConversationTurn
from routedeck_core.contracts.events import EventPage, RouteDeckEvent
from routedeck_core.contracts.failures import RouteDeckFailure
from routedeck_core.contracts.session import (
    AttemptTerminalState,
    JournaledExecutionResult,
    OperationAttempt,
    PendingReview,
    RouteDeckSession,
    SessionSnapshot,
)
from routedeck_core.ports.session_store import RouteDeckSessionStore
from routedeck_core.state.leases import ExecutionClaim, TurnClaim, TurnLease
from routedeck_testing.conformance import assert_session_store_conforms


EXPECTED_PARAMETERS = {
    "create": ("self", "initial"),
    "load": ("self", "session_id"),
    "find_attempt": ("self", "session_id", "request_id"),
    "acquire_turn": ("self", "claim"),
    "stage_review": ("self", "lease", "review"),
    "claim_execution": ("self", "lease", "attempt"),
    "record_execution_result": ("self", "claim", "result"),
    "commit_state": (
        "self",
        "lease",
        "expected_session_version",
        "next_state",
        "events",
    ),
    "finalize_turn": (
        "self",
        "lease",
        "expected_session_version",
        "next_state",
        "turns",
        "events",
    ),
    "interrupt_turn": (
        "self",
        "lease",
        "expected_session_version",
        "next_state",
        "failure",
        "events",
    ),
    "commit_attempt": (
        "self",
        "lease",
        "expected_session_version",
        "next_state",
        "events",
        "terminal",
    ),
    "mark_external_outcome_unknown": ("self", "claim", "failure"),
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
    ),
}

EXPECTED_RETURNS = {
    "create": SessionSnapshot,
    "load": SessionSnapshot,
    "find_attempt": OperationAttempt | None,
    "acquire_turn": TurnLease,
    "stage_review": SessionSnapshot,
    "claim_execution": ExecutionClaim,
    "record_execution_result": type(None),
    "commit_state": SessionSnapshot,
    "finalize_turn": SessionSnapshot,
    "interrupt_turn": SessionSnapshot,
    "commit_attempt": SessionSnapshot,
    "mark_external_outcome_unknown": SessionSnapshot,
    "release_turn": type(None),
    "events_after": EventPage,
    "load_private_blob": bytes | None,
    "save_private_blob": SessionSnapshot,
}


class CompleteStoreDouble:
    async def create(self, initial: RouteDeckSession) -> SessionSnapshot:
        raise AssertionError("conformance must not execute store methods")

    async def load(self, session_id: str) -> SessionSnapshot:
        raise AssertionError("conformance must not execute store methods")

    async def find_attempt(
        self, session_id: str, request_id: str
    ) -> OperationAttempt | None:
        raise AssertionError("conformance must not execute store methods")

    async def acquire_turn(self, claim: TurnClaim) -> TurnLease:
        raise AssertionError("conformance must not execute store methods")

    async def stage_review(
        self, lease: TurnLease, review: PendingReview
    ) -> SessionSnapshot:
        raise AssertionError("conformance must not execute store methods")

    async def claim_execution(
        self, lease: TurnLease, attempt: OperationAttempt
    ) -> ExecutionClaim:
        raise AssertionError("conformance must not execute store methods")

    async def record_execution_result(
        self, claim: ExecutionClaim, result: JournaledExecutionResult
    ) -> None:
        raise AssertionError("conformance must not execute store methods")

    async def commit_state(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
    ) -> SessionSnapshot:
        raise AssertionError("conformance must not execute store methods")

    async def finalize_turn(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        turns: Sequence[FinalizedConversationTurn],
        events: Sequence[RouteDeckEvent],
    ) -> SessionSnapshot:
        raise AssertionError("conformance must not execute store methods")

    async def interrupt_turn(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        failure: RouteDeckFailure,
        events: Sequence[RouteDeckEvent],
    ) -> SessionSnapshot:
        raise AssertionError("conformance must not execute store methods")

    async def commit_attempt(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
        terminal: AttemptTerminalState,
    ) -> SessionSnapshot:
        raise AssertionError("conformance must not execute store methods")

    async def mark_external_outcome_unknown(
        self, claim: ExecutionClaim, failure: RouteDeckFailure
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
