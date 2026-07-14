from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import SecretStr

from routedeck_core.app import (
    ApplicationSpec,
    FeatureBindings,
    FeatureSpec,
    bind_app,
    compile_app,
)
from routedeck_core.contracts.application import CapabilitySpec, NodeSpec
from routedeck_core.contracts.conversation import FinalizedConversationTurn
from routedeck_core.contracts.events import RouteDeckEvent, EventPage
from routedeck_core.contracts.failures import RouteDeckFailure
from routedeck_core.contracts.navigation import (
    DeepLinkPolicy,
    NodeKind,
    RecoveryPolicySpec,
    RouteSpec,
    TransitionSpec,
)
from routedeck_core.contracts.mutations import MutationCommit, MutationRecord
from routedeck_core.contracts.operations import (
    ContextProviderSpec,
    DeliveryPhase,
    EntityInputSpec,
    EntityProviderSpec,
    GuardSpec,
    OperationEvidence,
    OperationOutcome,
    OperationPhase,
    OperationRef,
    OperationSpec,
    ProviderRef,
    ReviewPolicy,
    SafetyClass,
)
from routedeck_core.contracts.projection import PublicEntityHandle
from routedeck_core.contracts.session import (
    JournaledExecutionResult,
    OperationAttempt,
    PendingReview,
    PrivateEntityBinding,
    PrivateSessionState,
    PublicSessionState,
    ReviewResolution,
    RouteDeckSession,
    SessionSnapshot,
    StoredOperationAttempt,
)
from routedeck_core.contracts.surfaces import SurfaceSlotsSpec, SurfaceSpec
from routedeck_core.ports.executor import (
    ExecutionContext,
    OperationBinding,
    OperationExecutor,
)
from routedeck_core.ports.session_store import SessionStoreError, SessionStoreErrorCode
from routedeck_core.state.leases import ExecutionClaim, TurnClaim, TurnLease
from routedeck_core.state.session import create_session
from routedeck_core.supervision.guards import (
    GuardDecision,
    GuardInvocationContext,
    ProviderInvocationContext,
    ProviderResult,
)


CONTEXT_PROVIDER = ContextProviderSpec(
    id="test.context",
    description="Mutable test-only authoritative context.",
    output_schema={
        "type": "object",
        "properties": {"revision": {"type": "integer"}},
        "required": ["revision"],
        "additionalProperties": False,
    },
)
ENTITY_PROVIDER = EntityProviderSpec(
    id="test.items",
    entity_kind="item",
    description="Test-only item bindings.",
    output_schema={
        "type": "object",
        "properties": {"revision": {"type": "integer"}},
        "required": ["revision"],
        "additionalProperties": False,
    },
)
ALLOWED_GUARD = GuardSpec(
    id="test.allowed",
    description="Mutable test-only guard.",
)
WRITE_OPERATION = OperationSpec(
    id="test.write",
    title="Write",
    description="Test-only write operation.",
    input_schema={
        "type": "object",
        "properties": {"quantity": {"type": "integer", "minimum": 1}},
        "required": ["quantity"],
        "additionalProperties": False,
    },
    safety_class=SafetyClass.WRITE_EXTERNAL,
    unknown_recovery_directive="Verify the write before retrying.",
    outcomes=("written",),
    outcome_schemas={
        "written": {
            "type": "object",
            "properties": {"receipt": {"type": "string"}},
            "additionalProperties": False,
        }
    },
    provider_refs=(CONTEXT_PROVIDER.ref,),
    guard_refs=(ALLOWED_GUARD.ref,),
)
BOUND_OPERATION = OperationSpec(
    id="test.bound_write",
    title="Bound write",
    description="Test-only entity-bound write operation.",
    input_schema={
        "type": "object",
        "properties": {"item_ref": {"type": "string"}},
        "required": ["item_ref"],
        "additionalProperties": False,
    },
    entity_inputs=(EntityInputSpec(argument_name="item_ref", entity_kind="item"),),
    safety_class=SafetyClass.WRITE_EXTERNAL,
    unknown_recovery_directive="Verify the entity write before retrying.",
    outcomes=("bound",),
    provider_refs=(ENTITY_PROVIDER.ref,),
    guard_refs=(ALLOWED_GUARD.ref,),
)
REVIEW_OPERATION = OperationSpec(
    id="test.reviewed_write",
    title="Reviewed write",
    description="Test-only reviewed write operation.",
    input_schema={
        "type": "object",
        "properties": {"quantity": {"type": "integer", "minimum": 1}},
        "required": ["quantity"],
        "additionalProperties": False,
    },
    safety_class=SafetyClass.WRITE_EXTERNAL,
    unknown_recovery_directive="Verify the reviewed write before retrying.",
    review_policy=ReviewPolicy.REQUIRED,
    outcomes=("reviewed",),
    provider_refs=(CONTEXT_PROVIDER.ref,),
    guard_refs=(ALLOWED_GUARD.ref,),
)
READ_OPERATION = OperationSpec(
    id="test.read",
    title="Read",
    description="Test-only external read.",
    safety_class=SafetyClass.READ_EXTERNAL,
    outcomes=("read",),
    provider_refs=(CONTEXT_PROVIDER.ref,),
    guard_refs=(ALLOWED_GUARD.ref,),
)
ACTIVE_SURFACE = SurfaceSpec(id="test.active", component="test.active")
CAPABILITY = CapabilitySpec(
    id="test.operations",
    title="Test operations",
    operations=(
        WRITE_OPERATION.ref,
        BOUND_OPERATION.ref,
        REVIEW_OPERATION.ref,
        READ_OPERATION.ref,
    ),
    surfaces=(ACTIVE_SURFACE.ref,),
)
START_NODE = NodeSpec(
    id="test.start",
    title="Start",
    kind=NodeKind.WORKFLOW,
    route=RouteSpec(template="/", deep_link_policy=DeepLinkPolicy.SHAREABLE),
    context_providers=(CONTEXT_PROVIDER,),
    entity_providers=(ENTITY_PROVIDER,),
    guards=(ALLOWED_GUARD,),
    operations=(WRITE_OPERATION, BOUND_OPERATION, REVIEW_OPERATION, READ_OPERATION),
    capabilities=(CAPABILITY,),
    surfaces=SurfaceSlotsSpec(active=ACTIVE_SURFACE),
    recovery=RecoveryPolicySpec(
        directives=(
            "Verify the write before retrying.",
            "Verify the entity write before retrying.",
            "Verify the reviewed write before retrying.",
        ),
        failure_surface=ACTIVE_SURFACE.ref,
    ),
)
TEST_APP_SPEC = ApplicationSpec(
    name="supervision-test",
    entry_node=START_NODE.ref,
    features=(
        FeatureSpec(
            namespace="test",
            nodes=(START_NODE,),
            transitions=tuple(
                TransitionSpec(
                    source=START_NODE.ref,
                    operation=operation.ref,
                    outcome=outcome,
                    target=START_NODE.ref,
                )
                for operation, outcome in (
                    (WRITE_OPERATION, "written"),
                    (BOUND_OPERATION, "bound"),
                    (REVIEW_OPERATION, "reviewed"),
                    (READ_OPERATION, "read"),
                )
            ),
        ),
    ),
)


@dataclass
class MutableProvider:
    values: dict[str, Any] = field(default_factory=lambda: {"revision": 1})
    calls: list[str] = field(default_factory=list)
    raises: Exception | None = None

    async def __call__(self, context: ProviderInvocationContext) -> ProviderResult:
        self.calls.append(context.request.request_id)
        if self.raises is not None:
            raise self.raises
        return ProviderResult(values=self.values)


@dataclass
class MutableGuard:
    decision: GuardDecision = field(default_factory=GuardDecision.allowed_result)
    calls: list[str] = field(default_factory=list)
    raises: Exception | None = None

    async def __call__(self, context: GuardInvocationContext) -> GuardDecision:
        self.calls.append(context.request.request_id)
        if self.raises is not None:
            raise self.raises
        return self.decision


@dataclass
class RecordingHandler:
    operation_id: str
    outcome: str
    calls: list[tuple[Mapping[str, Any], ExecutionContext]] = field(
        default_factory=list
    )
    next_outcome: OperationOutcome | None = None
    raises: BaseException | None = None
    started_event: asyncio.Event | None = None
    release_event: asyncio.Event | None = None

    async def __call__(
        self,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> OperationOutcome:
        self.calls.append((arguments, context))
        if self.started_event is not None:
            self.started_event.set()
        if self.release_event is not None:
            await self.release_event.wait()
        if self.raises is not None:
            raise self.raises
        return self.next_outcome or OperationOutcome(
            outcome=self.outcome,
            delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
            observation={},
        )


@dataclass
class RecordingExecutor(OperationExecutor):
    calls: list[OperationBinding] = field(default_factory=list)

    async def execute(
        self,
        binding: OperationBinding,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> OperationOutcome:
        self.calls.append(binding)
        return await binding.handler(arguments, context)

    def call_count(self, operation_id: str) -> int:
        return sum(binding.operation.id == operation_id for binding in self.calls)


@dataclass
class FixedClock:
    current: datetime = datetime(2029, 1, 1, tzinfo=UTC)

    def now(self) -> datetime:
        return self.current

    def advance(self, duration: timedelta) -> None:
        self.current += duration


@dataclass
class RecordingNotifier:
    notifications: list[tuple[str, tuple[RouteDeckEvent, ...]]] = field(
        default_factory=list
    )

    async def notify(
        self,
        session_id: str,
        events: Sequence[RouteDeckEvent],
    ) -> None:
        self.notifications.append((session_id, tuple(events)))


@dataclass
class SequentialIds:
    counters: Counter[str] = field(default_factory=Counter)

    def __call__(self, kind: str) -> str:
        self.counters[kind] += 1
        return f"{kind}-{self.counters[kind]}"


class InMemorySessionStore:
    """Explicit test double for Task 5; product code never imports this class."""

    def __init__(self, session: RouteDeckSession) -> None:
        self.sessions = {session.session_id: session}
        self.attempts: dict[tuple[str, str], StoredOperationAttempt] = {}
        self.reviews: dict[tuple[str, str], PendingReview] = {}
        self.active_leases: dict[str, TurnLease] = {}
        self.turn_claims: dict[str, TurnClaim] = {}
        self.mutations: dict[tuple[str, str], MutationRecord] = {}
        self.creation_requests: dict[str, tuple[str, str]] = {}
        self.execution_claims: dict[str, ExecutionClaim] = {}
        self.turn_claim_counts: Counter[str] = Counter()
        self.child_attempts: dict[str, list[str]] = {}
        self.active_children: dict[str, str] = {}
        self.fail_record_result = False
        self.fail_record_started_once = False
        self.fail_mark_unknown_once = False
        self.fail_commit_attempt_once = False
        self.fail_release_turn_once = False
        self.fail_release_child_once = False
        self._failed_commit = False
        self._failed_start = False
        self._failed_unknown = False
        self._failed_release_turn = False
        self._failed_release_child = False

    async def create(self, initial: RouteDeckSession) -> SessionSnapshot:
        self.sessions[initial.session_id] = initial
        return SessionSnapshot(state=initial)

    async def create_for_request(
        self,
        initial: RouteDeckSession,
        request_id: str,
        request_fingerprint: str,
    ) -> SessionSnapshot:
        existing = self.creation_requests.get(request_id)
        if existing is not None:
            fingerprint, session_id = existing
            if fingerprint != request_fingerprint:
                raise SessionStoreError(SessionStoreErrorCode.REQUEST_ID_REUSED)
            return await self.load(session_id)
        snapshot = await self.create(initial)
        self.creation_requests[request_id] = (
            request_fingerprint,
            initial.session_id,
        )
        return snapshot

    async def load(self, session_id: str) -> SessionSnapshot:
        return SessionSnapshot(state=self.sessions[session_id])

    async def find_attempt(
        self, session_id: str, request_id: str
    ) -> StoredOperationAttempt | None:
        return self.attempts.get((session_id, request_id))

    async def find_review(
        self, session_id: str, review_id: str
    ) -> PendingReview | None:
        return self.reviews.get((session_id, review_id))

    async def find_mutation(
        self,
        session_id: str,
        request_id: str,
    ) -> MutationRecord | None:
        return self.mutations.get((session_id, request_id))

    async def acquire_turn(self, claim: TurnClaim) -> TurnLease:
        if claim.session_id in self.active_leases:
            raise SessionStoreError(SessionStoreErrorCode.OPERATION_IN_PROGRESS)
        self._require_version(claim.session_id, claim.expected_session_version)
        lease = TurnLease(
            capability=SecretStr(f"lease:{claim.request_id}"),
            fencing_token=self.turn_claim_counts[claim.request_id] + 1,
            session_id=claim.session_id,
            request_id=claim.request_id,
        )
        self.active_leases[claim.session_id] = lease
        self.turn_claims[claim.session_id] = claim
        self.turn_claim_counts[claim.request_id] += 1
        return lease

    async def claim_child_attempt(
        self,
        lease: TurnLease,
        request_id: str,
        request_fingerprint: str,
    ) -> None:
        del request_fingerprint
        self._require_lease(lease)
        if lease.session_id in self.active_children:
            raise SessionStoreError(SessionStoreErrorCode.OPERATION_IN_PROGRESS)
        self.active_children[lease.session_id] = request_id

    async def release_child_attempt(
        self,
        lease: TurnLease,
        request_id: str,
    ) -> None:
        self._require_lease(lease)
        if self.fail_release_child_once and not self._failed_release_child:
            self._failed_release_child = True
            raise SessionStoreError(SessionStoreErrorCode.PERSISTENCE_FAILURE)
        if self.active_children.get(lease.session_id) != request_id:
            raise SessionStoreError(SessionStoreErrorCode.LEASE_MISMATCH)
        del self.active_children[lease.session_id]

    async def stage_review(
        self,
        lease: TurnLease,
        expected_session_version: int,
        record: StoredOperationAttempt,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
        parent_mutation: MutationCommit | None = None,
    ) -> SessionSnapshot:
        self._require_lease(lease)
        self._require_version(lease.session_id, expected_session_version)
        del events
        if record.review is None:
            raise RuntimeError("test review record missing review")
        self.sessions[lease.session_id] = next_state
        if parent_mutation is not None:
            self._record_mutation(lease, parent_mutation, next_state)
        self.attempts[(lease.session_id, record.attempt.request_id)] = record
        self.reviews[(lease.session_id, record.review.review_id)] = record.review
        return SessionSnapshot(state=next_state)

    async def claim_execution(
        self, lease: TurnLease, record: StoredOperationAttempt
    ) -> ExecutionClaim:
        self._require_lease(lease)
        attempt = record.attempt
        if attempt.attempt_id in self.execution_claims:
            raise RuntimeError("test execution already claimed")
        if attempt.resumed_review_id is not None:
            key = (lease.session_id, attempt.resumed_review_id)
            review = self.reviews[key]
            if review.resolution is not ReviewResolution.PENDING:
                raise SessionStoreError(SessionStoreErrorCode.REVIEW_ALREADY_RESOLVED)
            if (
                record.review is None
                or record.review.resolution is not ReviewResolution.ACCEPTED
            ):
                raise RuntimeError("test accepted review record missing")
            self.reviews[key] = record.review
            proposal_key = (lease.session_id, review.attempt.request_id)
            proposal_record = self.attempts[proposal_key]
            self.attempts[proposal_key] = proposal_record.model_copy(
                update={"review": record.review}
            )
        claim = ExecutionClaim(
            capability=SecretStr(f"execution:{attempt.attempt_id}"),
            fencing_token=lease.fencing_token,
            session_id=lease.session_id,
            request_id=attempt.request_id,
            attempt_id=attempt.attempt_id,
        )
        self.execution_claims[attempt.attempt_id] = claim
        self.attempts[(lease.session_id, attempt.request_id)] = record
        if attempt.parent_turn_id is not None:
            if self.active_children.get(lease.session_id) != attempt.request_id:
                raise SessionStoreError(SessionStoreErrorCode.LEASE_MISMATCH)
            self.child_attempts.setdefault(attempt.parent_turn_id, []).append(
                attempt.request_id
            )
        return claim

    async def recover_execution_claim(
        self,
        lease: TurnLease,
        attempt_id: str,
    ) -> ExecutionClaim:
        self._require_lease(lease)
        previous = self.execution_claims[attempt_id]
        if previous.session_id != lease.session_id:
            raise SessionStoreError(SessionStoreErrorCode.LEASE_MISMATCH)
        recovered = previous.model_copy(
            update={
                "capability": SecretStr(f"recovery:{attempt_id}:{lease.fencing_token}"),
                "fencing_token": lease.fencing_token,
            }
        )
        self.execution_claims[attempt_id] = recovered
        return recovered

    async def record_execution_started(
        self,
        claim: ExecutionClaim,
        record: StoredOperationAttempt,
    ) -> None:
        self._require_claim(claim)
        if self.fail_record_started_once and not self._failed_start:
            self._failed_start = True
            raise OSError("test start evidence unavailable")
        self.attempts[(claim.session_id, claim.request_id)] = record

    async def record_execution_result(
        self,
        claim: ExecutionClaim,
        result: JournaledExecutionResult,
        record: StoredOperationAttempt,
    ) -> None:
        self._require_claim(claim)
        if self.fail_record_result:
            raise OSError("test journal unavailable")
        if record.journaled_result != result:
            raise RuntimeError("test journal record mismatch")
        self.attempts[(claim.session_id, claim.request_id)] = record

    async def commit_state(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
        mutation: MutationCommit,
    ) -> SessionSnapshot:
        self._require_lease(lease)
        self._require_version(lease.session_id, expected_session_version)
        del events
        self.sessions[lease.session_id] = next_state
        self._record_mutation(lease, mutation, next_state)
        return SessionSnapshot(state=next_state)

    async def finalize_turn(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        turns: Sequence[FinalizedConversationTurn],
        events: Sequence[RouteDeckEvent],
        mutation: MutationCommit,
    ) -> SessionSnapshot:
        del turns, events
        self._require_lease(lease)
        if lease.session_id in self.active_children:
            raise SessionStoreError(SessionStoreErrorCode.OPERATION_IN_PROGRESS)
        self._require_version(lease.session_id, expected_session_version)
        self.sessions[lease.session_id] = next_state
        self._record_mutation(lease, mutation, next_state)
        await self.release_turn(lease)
        return SessionSnapshot(state=next_state)

    async def interrupt_turn(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        failure: RouteDeckFailure,
        events: Sequence[RouteDeckEvent],
        mutation: MutationCommit,
    ) -> SessionSnapshot:
        del failure, events
        self._require_lease(lease)
        if lease.session_id in self.active_children:
            raise SessionStoreError(SessionStoreErrorCode.OPERATION_IN_PROGRESS)
        self._require_version(lease.session_id, expected_session_version)
        self.sessions[lease.session_id] = next_state
        self._record_mutation(lease, mutation, next_state)
        await self.release_turn(lease)
        return SessionSnapshot(state=next_state)

    async def commit_attempt(
        self,
        claim: ExecutionClaim,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
        record: StoredOperationAttempt,
    ) -> SessionSnapshot:
        self._require_claim(claim)
        self._require_version(claim.session_id, expected_session_version)
        del events
        if self.fail_commit_attempt_once and not self._failed_commit:
            self._failed_commit = True
            raise OSError("test state commit unavailable")
        if record.attempt.attempt_id != claim.attempt_id:
            raise RuntimeError("test commit attempt mismatch")
        self.sessions[claim.session_id] = next_state
        self.attempts[(claim.session_id, record.attempt.request_id)] = record
        if record.review is not None:
            self.reviews[(claim.session_id, record.review.review_id)] = record.review
        return SessionSnapshot(state=next_state)

    async def commit_supervision(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
        record: StoredOperationAttempt,
    ) -> SessionSnapshot:
        self._require_lease(lease)
        self._require_version(lease.session_id, expected_session_version)
        del events
        self.sessions[lease.session_id] = next_state
        self.attempts[(lease.session_id, record.attempt.request_id)] = record
        if record.review is not None:
            self.reviews[(lease.session_id, record.review.review_id)] = record.review
            proposal_key = (lease.session_id, record.review.attempt.request_id)
            proposal_record = self.attempts.get(proposal_key)
            if proposal_record is not None:
                self.attempts[proposal_key] = proposal_record.model_copy(
                    update={"review": record.review}
                )
        return SessionSnapshot(state=next_state)

    async def mark_external_outcome_unknown(
        self,
        claim: ExecutionClaim,
        expected_session_version: int,
        record: StoredOperationAttempt,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
    ) -> SessionSnapshot:
        self._require_claim(claim)
        self._require_version(claim.session_id, expected_session_version)
        del events
        if self.fail_mark_unknown_once and not self._failed_unknown:
            self._failed_unknown = True
            raise OSError("test unknown-state commit unavailable")
        self.sessions[claim.session_id] = next_state
        self.attempts[(claim.session_id, record.attempt.request_id)] = record
        return SessionSnapshot(state=next_state)

    async def release_turn(self, lease: TurnLease) -> None:
        self._require_lease(lease)
        if self.fail_release_turn_once and not self._failed_release_turn:
            self._failed_release_turn = True
            raise SessionStoreError(SessionStoreErrorCode.PERSISTENCE_FAILURE)
        self.active_children.pop(lease.session_id, None)
        del self.active_leases[lease.session_id]
        self.turn_claims.pop(lease.session_id, None)

    async def events_after(self, session_id: str, cursor: int, limit: int) -> EventPage:
        del session_id, limit
        return EventPage(events=(), next_cursor=cursor, has_more=False)

    async def load_private_blob(self, session_id: str, form_id: str) -> bytes | None:
        del session_id, form_id
        return None

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
        del form_id, encrypted_value
        return await self.commit_state(
            lease,
            expected_session_version,
            next_state,
            events,
            mutation,
        )

    def active_turn(self, request_id: str) -> TurnLease | None:
        return next(
            (
                lease
                for lease in self.active_leases.values()
                if lease.request_id == request_id
            ),
            None,
        )

    def _require_lease(self, lease: TurnLease) -> None:
        if self.active_leases.get(lease.session_id) != lease:
            raise SessionStoreError(SessionStoreErrorCode.LEASE_MISMATCH)

    def _require_claim(self, claim: ExecutionClaim) -> None:
        if self.execution_claims.get(claim.attempt_id) != claim:
            raise SessionStoreError(SessionStoreErrorCode.LEASE_MISMATCH)

    def _record_mutation(
        self,
        lease: TurnLease,
        mutation: MutationCommit,
        state: RouteDeckSession,
    ) -> None:
        claim = self.turn_claims[lease.session_id]
        self.mutations[(lease.session_id, lease.request_id)] = MutationRecord(
            **mutation.model_dump(mode="python"),
            session_id=lease.session_id,
            request_id=lease.request_id,
            request_fingerprint=claim.request_fingerprint,
            committed_session_version=state.session_version,
            committed_projection_version=state.projection_version,
            committed_event_cursor=state.event_cursor,
        )

    def _require_version(self, session_id: str, expected: int) -> None:
        if self.sessions[session_id].session_version != expected:
            raise SessionStoreError(SessionStoreErrorCode.VERSION_CONFLICT)

    @staticmethod
    def _evidence(
        attempt: OperationAttempt,
        phases: tuple[OperationPhase, ...],
        *,
        result: JournaledExecutionResult | None = None,
    ) -> OperationEvidence:
        return OperationEvidence(
            source=attempt.source,
            phases=phases,
            attempt_id=attempt.attempt_id,
            request_fingerprint=attempt.request_fingerprint,
            delivery_phase=result.delivery_phase if result is not None else None,
            result_id=result.result_id if result is not None else None,
            result_fingerprint=(
                result.result_fingerprint if result is not None else None
            ),
        )


@pytest.fixture
def provider() -> MutableProvider:
    return MutableProvider()


@pytest.fixture
def guard() -> MutableGuard:
    return MutableGuard()


@pytest.fixture
def handlers() -> dict[str, RecordingHandler]:
    return {
        "test.write": RecordingHandler("test.write", "written"),
        "test.bound_write": RecordingHandler("test.bound_write", "bound"),
        "test.reviewed_write": RecordingHandler("test.reviewed_write", "reviewed"),
        "test.read": RecordingHandler("test.read", "read"),
    }


@pytest.fixture
def compiled_app():
    return compile_app(TEST_APP_SPEC)


@pytest.fixture
def bound_app(compiled_app, provider, guard, handlers):
    return bind_app(
        compiled_app,
        FeatureBindings(
            handlers={
                OperationRef(id=operation_id): handler
                for operation_id, handler in handlers.items()
            },
            providers={
                ProviderRef(id="test.context"): provider,
                ProviderRef(id="test.items"): provider,
            },
            guards={ALLOWED_GUARD.ref: guard},
        ),
    )


@pytest.fixture
def canonical_session(compiled_app) -> RouteDeckSession:
    return create_session(
        app=compiled_app,
        session_id="session-1",
        private_state=PrivateSessionState(
            entity_bindings=(
                PrivateEntityBinding(
                    entity_kind="item",
                    public_handle="item-public-1",
                    private_id="private-item-sentinel",
                    allowed_operation_ids=("test.bound_write",),
                ),
            )
        ),
        public_state=PublicSessionState(
            entity_handles=(
                PublicEntityHandle(entity_kind="item", handle="item-public-1"),
            )
        ),
    )


@pytest.fixture
def store(canonical_session) -> InMemorySessionStore:
    return InMemorySessionStore(canonical_session)


@pytest.fixture
def executor() -> RecordingExecutor:
    return RecordingExecutor()


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock()


@pytest.fixture
def notifier() -> RecordingNotifier:
    return RecordingNotifier()


@pytest.fixture
def ids() -> SequentialIds:
    return SequentialIds()


@pytest.fixture
def runner_factory(bound_app, store, executor, clock, notifier, ids):
    def factory(**overrides):
        from routedeck_core.supervision.runner import RouteDeckOperationRunner

        values = {
            "app": bound_app,
            "store": store,
            "executor": executor,
            "clock": clock,
            "notifier": notifier,
            "id_factory": ids,
            "review_ttl": timedelta(minutes=10),
            "resume_capability_ttl": timedelta(hours=24),
            "default_session_id": "session-1",
        }
        values.update(overrides)
        return RouteDeckOperationRunner(**values)

    return factory


@pytest.fixture
def runner(runner_factory):
    return runner_factory()
