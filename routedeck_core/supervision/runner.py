from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Any


from ..app.bindings import BoundRouteDeckApp
from ..contracts.conversation import (
    ConversationRole,
    ConversationToolCall,
    FinalizedConversationTurn,
)
from ..contracts.failures import FailureKind, FailureSafeDetails, RouteDeckFailure
from ..contracts.operations import (
    DeliveryPhase,
    OperationDisposition,
    OperationEvidence,
    OperationPhase,
    OperationRequest,
    OperationResult,
    OperationSource,
    OperationSpec,
    ReviewPolicy,
)
from ..contracts.projection import FrozenJson
from ..contracts.session import (
    AttemptTerminalState,
    JournaledExecutionResult,
    Location,
    OperationArgument,
    OperationAttempt,
    OperationAttemptStatus,
    OperationState,
    RouteDeckSession,
    StoredOperationAttempt,
)
from ..ports.clock import Clock
from ..ports.executor import (
    OperationExecutor,
)
from ..ports.notifier import RouteDeckNotifier, notify_event_wakeup
from ..ports.session_store import (
    RouteDeckSessionStore,
    SessionStoreError,
)
from ..state.leases import TurnClaim, TurnLease, TurnOwnerKind
from ..state.reducer import (
    OperationStateStored,
    PublicEventsRecorded,
    PublicSessionStateStored,
    reduce_session_batch,
)
from .guards import (
    SupervisionPolicyMixin,
)
from .outcomes import (
    OutcomeLifecycleMixin,
    canonical_json_fingerprint,
    canonical_request_fingerprint,
)
from .reviews import ReviewLifecycleMixin
from .turns import TurnLifecycleMixin


IdFactory = Callable[[str], str]


@dataclass(frozen=True)
class RouteEntryInvocation:
    """Structurally matched route entry passed to the supervised operation path."""

    location: Location


class RouteDeckOperationRunner(
    ReviewLifecycleMixin,
    OutcomeLifecycleMixin,
    TurnLifecycleMixin,
    SupervisionPolicyMixin,
):
    """Run every product operation through one product-neutral supervision path."""

    def __init__(
        self,
        *,
        app: BoundRouteDeckApp,
        store: RouteDeckSessionStore,
        executor: OperationExecutor,
        clock: Clock,
        notifier: RouteDeckNotifier,
        id_factory: IdFactory,
        review_ttl: timedelta,
        resume_capability_ttl: timedelta,
        default_session_id: str,
    ) -> None:
        if review_ttl <= timedelta(0):
            raise ValueError("review_ttl must be positive")
        if resume_capability_ttl <= timedelta(0):
            raise ValueError("resume_capability_ttl must be positive")
        if not default_session_id:
            raise ValueError("default_session_id must be non-empty")
        self.app = app
        self.store = store
        self.executor = executor
        self.clock = clock
        self.notifier = notifier
        self.id_factory = id_factory
        self.review_ttl = review_ttl
        self.resume_capability_ttl = resume_capability_ttl
        self.default_session_id = default_session_id

    async def run(
        self,
        request: OperationRequest,
        *,
        turn: TurnLease | None = None,
        review_turns: Sequence[FinalizedConversationTurn] = (),
        review_tool_call: ConversationToolCall | None = None,
        route_entry: RouteEntryInvocation | None = None,
    ) -> OperationResult:
        finalized_review_turns = tuple(review_turns)
        invalid_review_turns = bool(finalized_review_turns) and (
            turn is None
            or request.source is not OperationSource.AGENT
            or review_tool_call is None
            or review_tool_call.name != request.operation_id
            or dict(review_tool_call.arguments) != dict(request.arguments)
            or finalized_review_turns[0].role is not ConversationRole.USER
            or any(
                not isinstance(item, FinalizedConversationTurn)
                or item.request_id != turn.request_id
                or (
                    index > 0
                    and (
                        item.role is not ConversationRole.TOOL
                        or item.tool_call is None
                        or item.tool_status is None
                    )
                )
                for index, item in enumerate(finalized_review_turns)
            )
        )
        if invalid_review_turns or (
            review_tool_call is not None and not finalized_review_turns
        ):
            raise ValueError(
                "review turns require one user marker, typed tool observations, "
                "and the active tool call from an agent parent turn"
            )
        if (request.source is OperationSource.ROUTE) != (route_entry is not None):
            raise ValueError(
                "Route operation sources require exactly one route entry invocation"
            )
        operation = self.app.app.operations.get(request.operation_id)
        fingerprint = canonical_request_fingerprint(
            request,
            entity_inputs=operation.entity_inputs if operation is not None else (),
            parent_turn_id=turn.request_id if turn is not None else None,
        )
        if route_entry is not None:
            fingerprint = canonical_json_fingerprint(
                "routedeck.route-entry-request.v1",
                {
                    "operation_fingerprint": fingerprint,
                    "node_id": route_entry.location.node_id,
                    "route_params": {
                        item.name: item.value
                        for item in route_entry.location.route_params
                    },
                },
            )
        stored = await self.store.find_attempt(request.session_id, request.request_id)
        if stored is not None:
            if stored.attempt.request_fingerprint != fingerprint:
                return self._failure_result(
                    request=request,
                    fingerprint=fingerprint,
                    attempt_id=stored.attempt.attempt_id,
                    session_version=(
                        stored.committed_session_version
                        if stored.committed_session_version is not None
                        else request.expected_session_version
                    ),
                    projection_version=(
                        stored.committed_projection_version
                        if stored.committed_projection_version is not None
                        else 0
                    ),
                    disposition=OperationDisposition.BLOCKED,
                    failure=self._failure(
                        request,
                        kind=FailureKind.STATE_CONFLICT,
                        code="request_id_reused",
                        phase="idempotency",
                        message="This request ID was already used for another operation.",
                    ),
                    phases=(OperationPhase.RECEIVED,),
                )
            replay = self._result_from_stored(stored, session_id=request.session_id)
            if (
                replay is not None
                and replay.disposition is not OperationDisposition.PENDING
            ):
                return replay
            return await self._recover_stored_attempt(
                request=request,
                operation=operation,
                stored=stored,
                fingerprint=fingerprint,
                route_entry=route_entry,
            )

        snapshot = await self.store.load(request.session_id)
        session = snapshot.state
        if operation is None:
            return self._preflight_failure(
                request,
                fingerprint,
                session,
                code="operation_not_available",
                message="That operation is not available.",
            )

        try:
            lease, owns_lease = await self._lease_for(
                request=request,
                fingerprint=fingerprint,
                turn=turn,
            )
        except SessionStoreError as error:
            return self._store_conflict_result(
                request=request,
                fingerprint=fingerprint,
                error=error,
            )
        attempt_id = self.id_factory("attempt")
        lease_released = False
        child_released = False
        try:
            snapshot = await self.store.load(request.session_id)
            commit_session = snapshot.state
            session = (
                self._route_entry_session(commit_session, request, route_entry)
                if route_entry is not None
                else commit_session
            )
            validation_failure = self._validate_request(
                session=session,
                request=request,
                operation=operation,
            )
            if validation_failure is not None:
                return self._failure_result(
                    request=request,
                    fingerprint=fingerprint,
                    attempt_id=attempt_id,
                    session_version=session.session_version,
                    projection_version=session.projection_version,
                    disposition=OperationDisposition.BLOCKED,
                    failure=validation_failure,
                    phases=(
                        OperationPhase.RECEIVED,
                        OperationPhase.LEASE_ACQUIRED,
                    ),
                )

            resolved_entities = self._resolve_entities(
                session=session,
                request=request,
                operation=operation,
            )
            if resolved_entities is None:
                return self._failure_result(
                    request=request,
                    fingerprint=fingerprint,
                    attempt_id=attempt_id,
                    session_version=session.session_version,
                    projection_version=session.projection_version,
                    disposition=OperationDisposition.BLOCKED,
                    failure=self._failure(
                        request,
                        kind=FailureKind.CONTRACT,
                        code="invalid_entity_reference",
                        phase="entity_validation",
                        message="An operation reference is invalid or unavailable.",
                    ),
                    phases=(
                        OperationPhase.RECEIVED,
                        OperationPhase.LEASE_ACQUIRED,
                    ),
                )

            attempt = OperationAttempt(
                attempt_id=attempt_id,
                request_id=request.request_id,
                request_fingerprint=fingerprint,
                operation_id=operation.id,
                source=request.source,
                expected_session_version=request.expected_session_version,
                arguments=tuple(
                    OperationArgument(name=name, value=FrozenJson(value))
                    for name, value in sorted(request.arguments.to_dict().items())
                ),
                parent_turn_id=turn.request_id if turn is not None else None,
            )

            provider_values, provider_failure = await self._refresh_context(
                session=session,
                request=request,
                operation=operation,
                attempt_id=attempt_id,
            )
            if provider_failure is not None:
                return await self._commit_supervision_failure(
                    request=request,
                    attempt=attempt,
                    session=commit_session,
                    lease=lease,
                    disposition=OperationDisposition.BLOCKED,
                    failure=provider_failure,
                    phases=(
                        OperationPhase.RECEIVED,
                        OperationPhase.LEASE_ACQUIRED,
                        OperationPhase.VALIDATED,
                    ),
                )

            context_fingerprint = self._context_fingerprint(
                provider_values=provider_values,
                resolved_entities=resolved_entities,
            )
            attempt = attempt.model_copy(
                update={"context_fingerprint": context_fingerprint}
            )
            guard_decision, guard_failure = await self._evaluate_guards(
                session=session,
                request=request,
                operation=operation,
                attempt_id=attempt_id,
                provider_values=provider_values,
                resolved_entities=resolved_entities,
            )
            if guard_failure is not None:
                return await self._commit_supervision_failure(
                    request=request,
                    attempt=attempt,
                    session=commit_session,
                    lease=lease,
                    disposition=OperationDisposition.BLOCKED,
                    failure=guard_failure,
                    phases=(
                        OperationPhase.RECEIVED,
                        OperationPhase.LEASE_ACQUIRED,
                        OperationPhase.VALIDATED,
                        OperationPhase.CONTEXT_REFRESHED,
                    ),
                )
            if guard_decision is not None and not guard_decision.allowed:
                if guard_decision.disposition is None or guard_decision.failure is None:
                    raise RuntimeError("Invalid denied guard decision")
                return await self._commit_supervision_failure(
                    request=request,
                    attempt=attempt,
                    session=commit_session,
                    lease=lease,
                    disposition=guard_decision.disposition,
                    failure=guard_decision.failure,
                    phases=(
                        OperationPhase.RECEIVED,
                        OperationPhase.LEASE_ACQUIRED,
                        OperationPhase.VALIDATED,
                        OperationPhase.CONTEXT_REFRESHED,
                    ),
                )

            if operation.review_policy is ReviewPolicy.REQUIRED:
                if route_entry is not None:
                    raise RuntimeError("Route entry operations cannot require review")
                result = await self._stage_review(
                    request=request,
                    operation=operation,
                    attempt=attempt,
                    session=session,
                    lease=lease,
                    provider_values=provider_values,
                    owns_lease=owns_lease,
                    review_turns=finalized_review_turns,
                    review_tool_call=review_tool_call,
                )
                if turn is not None:
                    await self.store.release_child_attempt(lease, request.request_id)
                    child_released = True
                await self.store.release_turn(lease)
                lease_released = True
                return result

            return await self._execute_attempt(
                request=request,
                operation=operation,
                attempt=attempt,
                session=session,
                lease=lease,
                provider_values=provider_values,
                resolved_entities=resolved_entities,
                commit_session=commit_session,
            )
        finally:
            if turn is not None and not child_released:
                await self.store.release_child_attempt(lease, request.request_id)
            if owns_lease and not lease_released:
                await self.store.release_turn(lease)

    async def _recover_stored_attempt(
        self,
        *,
        request: OperationRequest,
        operation: OperationSpec | None,
        stored: StoredOperationAttempt,
        fingerprint: str,
        route_entry: RouteEntryInvocation | None,
    ) -> OperationResult:
        current = (await self.store.load(request.session_id)).state
        try:
            lease = await self.store.acquire_turn(
                TurnClaim(
                    session_id=request.session_id,
                    expected_session_version=current.session_version,
                    request_id=request.request_id,
                    request_fingerprint=fingerprint,
                    owner_kind=TurnOwnerKind.SYSTEM,
                )
            )
        except SessionStoreError as error:
            if (
                error.code.value == "operation_in_progress"
                and stored.disposition is OperationDisposition.PENDING
            ):
                replay = self._result_from_stored(
                    stored,
                    session_id=request.session_id,
                )
                if replay is None:
                    raise RuntimeError(
                        "Pending attempts require observed durable versions"
                    ) from error
                return replay
            return self._store_conflict_result(
                request=request,
                fingerprint=fingerprint,
                error=error,
            )
        try:
            claim = await self.store.recover_execution_claim(
                lease, stored.attempt.attempt_id
            )
            commit_session = (await self.store.load(request.session_id)).state
            session = (
                self._route_entry_session(commit_session, request, route_entry)
                if route_entry is not None
                else commit_session
            )
            if stored.journaled_result is not None:
                if operation is None:
                    raise RuntimeError(
                        "Stored execution cannot recover without its operation spec"
                    )
                if stored.journaled_result.failure is not None:
                    return await self._commit_failure(
                        request=request,
                        attempt=stored.attempt,
                        session=commit_session,
                        claim=claim,
                        result=stored.journaled_result,
                        recorded_record=stored,
                    )
                return await self._commit_success(
                    request=request,
                    operation=operation,
                    attempt=stored.attempt,
                    session=session,
                    commit_session=commit_session,
                    claim=claim,
                    result=stored.journaled_result,
                    recorded_record=stored,
                )
            phases = stored.evidence.phases if stored.evidence is not None else ()
            if (
                stored.attempt.status is OperationAttemptStatus.TOOL_STARTED
                or OperationPhase.TOOL_STARTED in phases
            ):
                if operation is None:
                    raise RuntimeError(
                        "Stored execution cannot recover without its operation spec"
                    )
                if not self._is_external_write(operation):
                    return await self._recover_non_write_started(
                        request=request,
                        operation=operation,
                        stored=stored,
                        session=commit_session,
                        claim=claim,
                    )
                return await self._mark_unknown(
                    request=request,
                    operation=operation,
                    attempt=stored.attempt,
                    claim=claim,
                    reason_code="tool_started_without_journal",
                    delivery_phase=DeliveryPhase.POSSIBLY_SENT,
                )
            return await self._commit_not_sent_recovery(
                request=request,
                stored=stored,
                session=commit_session,
                claim=claim,
            )
        finally:
            await self.store.release_turn(lease)

    async def _commit_not_sent_recovery(
        self,
        *,
        request: OperationRequest,
        stored: StoredOperationAttempt,
        session: RouteDeckSession,
        claim: Any,
    ) -> OperationResult:
        failure = self._failure(
            request,
            kind=FailureKind.PERSISTENCE,
            code="execution_interrupted_not_sent",
            phase="execution_recovery",
            message="The operation was interrupted before it was sent.",
            delivery_phase=DeliveryPhase.NOT_SENT,
        )
        attempt = stored.attempt.model_copy(
            update={
                "status": OperationAttemptStatus.INTERRUPTED,
                "terminal": AttemptTerminalState.INTERRUPTED,
                "failure": failure,
            }
        )
        public_state = session.public_state.model_copy(
            update={
                "status_code": failure.code,
                "status_message": failure.public_message,
                "failure": failure,
            }
        )
        next_state = reduce_session_batch(
            session,
            (
                OperationStateStored(operation=OperationState(active_attempt=attempt)),
                PublicSessionStateStored(state=public_state),
                PublicEventsRecorded(count=1),
            ),
        )
        event = self._operation_event(next_state, request, public_state)
        phases = (
            *self._supervised_phases(),
            OperationPhase.EXECUTION_CLAIMED,
            OperationPhase.STATE_COMMITTED,
            OperationPhase.COMPLETED,
        )
        evidence = self._evidence(
            attempt,
            phases,
            delivery_phase=DeliveryPhase.NOT_SENT,
        )
        record = stored.model_copy(
            update={
                "attempt": attempt,
                "disposition": OperationDisposition.FAILED,
                "evidence": evidence,
                "committed_session_version": next_state.session_version,
                "committed_projection_version": next_state.projection_version,
                "failure": failure,
            }
        )
        snapshot = await self.store.commit_attempt(
            claim,
            session.session_version,
            next_state,
            (event,),
            record,
        )
        await notify_event_wakeup(self.notifier, session.session_id, (event,))
        return self._failure_result(
            request=request,
            fingerprint=stored.attempt.request_fingerprint,
            attempt_id=stored.attempt.attempt_id,
            session_version=snapshot.session_version,
            projection_version=snapshot.projection_version,
            disposition=OperationDisposition.FAILED,
            failure=failure,
            phases=phases,
            delivery_phase=DeliveryPhase.NOT_SENT,
        )

    async def _lease_for(
        self,
        *,
        request: OperationRequest,
        fingerprint: str,
        turn: TurnLease | None,
    ) -> tuple[TurnLease, bool]:
        if turn is not None:
            if turn.session_id != request.session_id:
                raise ValueError("Turn lease does not belong to the request session")
            await self.store.claim_child_attempt(
                turn,
                request.request_id,
                fingerprint,
            )
            return turn, False
        owner = {
            OperationSource.SURFACE: TurnOwnerKind.SURFACE,
            OperationSource.AGENT: TurnOwnerKind.CHAT,
            OperationSource.SYSTEM: TurnOwnerKind.SYSTEM,
            OperationSource.ROUTE: TurnOwnerKind.NAVIGATION,
        }[request.source]
        lease = await self.store.acquire_turn(
            TurnClaim(
                session_id=request.session_id,
                expected_session_version=request.expected_session_version,
                request_id=request.request_id,
                request_fingerprint=fingerprint,
                owner_kind=owner,
            )
        )
        return lease, True

    def _route_entry_session(
        self,
        session: RouteDeckSession,
        request: OperationRequest,
        invocation: RouteEntryInvocation,
    ) -> RouteDeckSession:
        location = invocation.location
        if location.entry_id is not None:
            raise ValueError(
                "Route entry locations cannot supply canonical history IDs"
            )
        node = next(
            (
                candidate
                for candidate in self.app.app.spec.nodes
                if candidate.id == location.node_id
            ),
            None,
        )
        if node is None or node.entry is None:
            raise ValueError("The matched route has no declared entry operation")
        if node.entry.operation.id != request.operation_id:
            raise ValueError("The route entry operation does not match the request")
        operation = self.app.app.operations.get(request.operation_id)
        if operation is None or self._is_external_write(operation):
            raise ValueError(
                "Route entry operations must be declared non-write operations"
            )
        if operation.review_policy is ReviewPolicy.REQUIRED:
            raise ValueError("Route entry operations cannot require review")
        route_params = {item.name: item.value for item in location.route_params}
        arguments = {
            binding.argument: route_params[binding.parameter]
            for binding in node.entry.bindings
        }
        if request.arguments.to_dict() != arguments:
            raise ValueError("Route entry arguments do not match their exact bindings")
        canonical = location.model_copy(
            update={"entry_id": session.next_history_entry_id}
        )
        return session.model_copy(
            update={
                "current": canonical,
                "back_stack": (*session.back_stack, session.current),
                "forward_stack": (),
                "next_history_entry_id": session.next_history_entry_id + 1,
            }
        )

    async def _commit_supervision_failure(
        self,
        *,
        request: OperationRequest,
        attempt: OperationAttempt,
        session: RouteDeckSession,
        lease: TurnLease,
        disposition: OperationDisposition,
        failure: RouteDeckFailure,
        phases: tuple[OperationPhase, ...],
        review: Any | None = None,
    ) -> OperationResult:
        if disposition not in {
            OperationDisposition.BLOCKED,
            OperationDisposition.NEEDS_INPUT,
            OperationDisposition.FAILED,
        }:
            raise RuntimeError("Supervision failures require a failure disposition")
        failed_attempt = attempt.model_copy(
            update={
                "status": OperationAttemptStatus.FAILED,
                "terminal": AttemptTerminalState.FAILED,
                "failure": failure,
            }
        )
        public_state = session.public_state.model_copy(
            update={
                "status_code": failure.code,
                "status_message": failure.public_message,
                "failure": failure,
            }
        )
        next_state = reduce_session_batch(
            session,
            (
                OperationStateStored(
                    operation=OperationState(
                        active_attempt=failed_attempt,
                        pending_review=review,
                    )
                ),
                PublicSessionStateStored(state=public_state),
                PublicEventsRecorded(count=1),
            ),
        )
        event = self._operation_event(next_state, request, public_state)
        final_phases = (
            *phases,
            OperationPhase.STATE_COMMITTED,
            OperationPhase.COMPLETED,
        )
        record = StoredOperationAttempt(
            attempt=failed_attempt,
            review=review,
            disposition=disposition,
            evidence=self._evidence(failed_attempt, final_phases),
            committed_session_version=next_state.session_version,
            committed_projection_version=next_state.projection_version,
            failure=failure,
        )
        snapshot = await self.store.commit_supervision(
            lease,
            session.session_version,
            next_state,
            (event,),
            record,
        )
        await notify_event_wakeup(self.notifier, session.session_id, (event,))
        return self._failure_result(
            request=request,
            fingerprint=attempt.request_fingerprint,
            attempt_id=attempt.attempt_id,
            session_version=snapshot.session_version,
            projection_version=snapshot.projection_version,
            disposition=disposition,
            failure=failure,
            phases=final_phases,
        )

    def _preflight_failure(
        self,
        request: OperationRequest,
        fingerprint: str,
        session: RouteDeckSession,
        *,
        code: str,
        message: str,
    ) -> OperationResult:
        return self._failure_result(
            request=request,
            fingerprint=fingerprint,
            attempt_id=self.id_factory("attempt"),
            session_version=session.session_version,
            projection_version=session.projection_version,
            disposition=OperationDisposition.BLOCKED,
            failure=self._failure(
                request,
                kind=FailureKind.CONTRACT,
                code=code,
                phase="operation_validation",
                message=message,
            ),
            phases=(OperationPhase.RECEIVED,),
        )

    def _failure(
        self,
        request: OperationRequest,
        *,
        kind: FailureKind,
        code: str,
        phase: str,
        message: str,
        delivery_phase: DeliveryPhase | None = None,
        recovery_directive: str | None = None,
    ) -> RouteDeckFailure:
        return RouteDeckFailure(
            kind=kind,
            code=code,
            phase=phase,
            correlation_id=self.id_factory("correlation"),
            operation_id=request.operation_id,
            request_id=request.request_id,
            public_message=message,
            recovery_directive=recovery_directive,
            safe_details=FailureSafeDetails(
                delivery_phase=(
                    delivery_phase.value if delivery_phase is not None else None
                )
            ),
        )

    def _failure_result(
        self,
        *,
        request: OperationRequest,
        fingerprint: str,
        attempt_id: str,
        session_version: int,
        projection_version: int,
        disposition: OperationDisposition,
        failure: RouteDeckFailure,
        phases: tuple[OperationPhase, ...],
        delivery_phase: DeliveryPhase | None = None,
        result: JournaledExecutionResult | None = None,
    ) -> OperationResult:
        return OperationResult(
            disposition=disposition,
            session_id=request.session_id,
            request_id=request.request_id,
            operation_id=request.operation_id,
            session_version=session_version,
            projection_version=projection_version,
            evidence=OperationEvidence(
                source=request.source,
                phases=phases,
                attempt_id=attempt_id,
                request_fingerprint=fingerprint,
                delivery_phase=delivery_phase,
                result_id=result.result_id if result is not None else None,
                result_fingerprint=(
                    result.result_fingerprint if result is not None else None
                ),
            ),
            failure=failure,
        )

    @staticmethod
    def _supervised_phases() -> tuple[OperationPhase, ...]:
        return (
            OperationPhase.RECEIVED,
            OperationPhase.LEASE_ACQUIRED,
            OperationPhase.VALIDATED,
            OperationPhase.CONTEXT_REFRESHED,
            OperationPhase.GUARDS_PASSED,
        )


__all__ = ["RouteDeckOperationRunner", "RouteEntryInvocation"]
