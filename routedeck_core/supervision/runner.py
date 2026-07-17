from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta


from ..app.bindings import BoundApplication
from ..contracts.conversation import (
    ConversationRole,
    ConversationToolCall,
    FinalizedConversationTurn,
)
from ..contracts.failures import FailureKind
from ..contracts.operations import (
    OperationDisposition,
    OperationPhase,
    OperationRequest,
    OperationResult,
    OperationSource,
    ReviewPolicy,
)
from ..contracts.projection import FrozenJson
from ..contracts.session import (
    OperationArgument,
    OperationAttempt,
)
from ..ports.clock import Clock
from ..ports.executor import (
    OperationExecutor,
)
from ..ports.notifier import RouteDeckNotifier
from ..ports.session_store import (
    RouteDeckSessionStore,
    SessionStoreError,
)
from ..state.leases import TurnLease
from .guards import (
    SupervisionPolicyMixin,
)
from .outcomes import (
    OutcomeLifecycleMixin,
    canonical_json_fingerprint,
    canonical_request_fingerprint,
)
from .reviews import ReviewLifecycleMixin
from .runner_contracts import IdFactory, RouteEntryInvocation
from .runner_recovery import RunnerRecoveryMixin
from .runner_support import RunnerSupportMixin
from .turns import TurnLifecycleMixin


class RouteDeckOperationRunner(
    ReviewLifecycleMixin,
    OutcomeLifecycleMixin,
    TurnLifecycleMixin,
    SupervisionPolicyMixin,
    RunnerRecoveryMixin,
    RunnerSupportMixin,
):
    """Run every product operation through one product-neutral supervision path."""

    def __init__(
        self,
        *,
        app: BoundApplication,
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

__all__ = ["RouteDeckOperationRunner", "RouteEntryInvocation"]
