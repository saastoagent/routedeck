from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from jsonschema.validators import validator_for

from ..contracts.events import (
    RouteDeckEvent,
    PublicEventPayload,
    RouteDeckEventType,
)
from ..contracts.effects import SessionEffects
from ..contracts.failures import FailureKind
from ..contracts.operations import (
    DeliveryPhase,
    OperationDisposition,
    OperationEvidence,
    OperationOutcome,
    OperationPhase,
    OperationRequest,
    OperationResult,
    OperationReview,
    Operation,
    SafetyClass,
)
from ..contracts.session import (
    JournaledExecutionResult,
    OperationAttempt,
    PublicSessionState,
    RouteDeckSession,
    SessionSnapshot,
    StoredOperationAttempt,
)
from ..state.effects import session_state_with_effects

from .fingerprints import canonical_json_fingerprint
from .outcome_base import OutcomeRuntimePorts


class OutcomeResultMixin(OutcomeRuntimePorts):
    def _journaled_result(
        self,
        request: OperationRequest,
        attempt: OperationAttempt,
        operation: Operation,
        outcome: OperationOutcome,
    ) -> JournaledExecutionResult:
        value = {
            "attempt_id": attempt.attempt_id,
            "request_id": request.request_id,
            "operation_id": operation.id,
            "outcome": outcome.outcome,
            "delivery_phase": outcome.delivery_phase.value,
            "observation": outcome.observation.to_dict(),
            "effects": outcome.effects.model_dump(mode="json"),
            "failure": (
                outcome.failure.model_dump(mode="json")
                if outcome.failure is not None
                else None
            ),
        }
        return JournaledExecutionResult(
            result_id=self.id_factory("result"),
            attempt_id=attempt.attempt_id,
            request_id=request.request_id,
            operation_id=operation.id,
            outcome=outcome.outcome,
            delivery_phase=outcome.delivery_phase,
            result_fingerprint=canonical_json_fingerprint(
                "routedeck.execution-result.v1",
                value,
            ),
            observation=outcome.observation,
            effects=outcome.effects,
            failure=outcome.failure,
        )

    def _valid_outcome_effects(
        self,
        *,
        session: RouteDeckSession,
        operation: Operation,
        outcome: OperationOutcome,
    ) -> bool:
        if outcome.outcome is None:
            if outcome.effects.is_empty:
                return True
            if (
                not self._is_external_write(operation)
                or outcome.failure is None
                or outcome.failure.kind is FailureKind.BUSINESS
                or outcome.delivery_phase is DeliveryPhase.NOT_SENT
                or outcome.effects.route_params is not None
            ):
                return False
            current = next(
                (
                    node
                    for node in self.app.app.graph.nodes
                    if node.id == session.current.node_id
                ),
                None,
            )
            if current is None:
                return False
            return self._valid_effects_for_node(
                session=session,
                effects=outcome.effects,
                target=current,
                allow_undeclared_empty_replacements=False,
            )
        transition = self._transition_for(
            node_id=session.current.node_id,
            operation_id=operation.id,
            outcome=outcome.outcome,
        )
        if transition is None:
            return outcome.effects.is_empty
        target = next(
            (
                node
                for node in self.app.app.graph.nodes
                if node.id == transition.target.id
            ),
            None,
        )
        if target is None:
            return False

        if not self._valid_effects_for_node(
            session=session,
            effects=outcome.effects,
            target=target,
            allow_undeclared_empty_replacements=True,
        ):
            return False

        expected_route_names = set(self.app.app.routes.path_parameter_names(target.id))
        if outcome.effects.route_params is None:
            if transition.target.id != session.current.node_id and expected_route_names:
                return False
        else:
            route_values = {
                parameter.name: parameter.value
                for parameter in outcome.effects.route_params
            }
            if set(route_values) != expected_route_names:
                return False
            try:
                self.app.app.routes.validate_path_bindings(
                    target.id,
                    route_values,
                )
            except Exception:
                return False

        try:
            session_state_with_effects(session, outcome.effects)
        except Exception:
            return False
        return True

    def _valid_effects_for_node(
        self,
        *,
        session: RouteDeckSession,
        effects: SessionEffects,
        target: Any,
        allow_undeclared_empty_replacements: bool,
    ) -> bool:
        target_entity_kinds = {
            provider.entity_kind for provider in target.entity_providers
        }
        target_operation_ids = {item.id for item in target.operations}
        for replacement in effects.replace_entities:
            if replacement.entity_kind not in target_entity_kinds and not (
                allow_undeclared_empty_replacements and not replacement.bindings
            ):
                return False
            for binding in replacement.bindings:
                if not set(binding.allowed_operation_ids) <= target_operation_ids:
                    return False

        surfaces = {
            surface.id: surface for surface in target.surfaces.declared_surfaces()
        }
        for update in effects.surface_updates:
            surface = surfaces.get(update.surface_id)
            if surface is None:
                return False
            values = {value.name: value.value.to_python() for value in update.values}
            if not self._valid_json_object(
                surface.public_props_schema_value(),
                values,
            ):
                return False
        try:
            session_state_with_effects(session, effects)
        except Exception:
            return False
        return True

    def _transition_for(
        self,
        *,
        node_id: str,
        operation_id: str,
        outcome: str,
    ) -> Any | None:
        return next(
            (
                candidate
                for candidate in self.app.app.graph.transitions
                if candidate.source.id == node_id
                and candidate.operation.id == operation_id
                and candidate.outcome == outcome
            ),
            None,
        )

    def _unknown_write_outcome(
        self,
        operation: Operation,
        outcome: OperationOutcome,
    ) -> bool:
        if not self._is_external_write(operation):
            return False
        if outcome.delivery_phase is DeliveryPhase.POSSIBLY_SENT:
            return True
        if (
            outcome.delivery_phase is DeliveryPhase.RESPONSE_RECEIVED
            and outcome.failure is not None
            and outcome.failure.kind is not FailureKind.BUSINESS
        ):
            return True
        if outcome.outcome is not None and outcome.outcome not in operation.outcomes:
            return outcome.delivery_phase is DeliveryPhase.RESPONSE_RECEIVED
        return False

    @staticmethod
    def _valid_outcome_observation(
        operation: Operation,
        outcome: OperationOutcome,
    ) -> bool:
        values = outcome.observation.to_dict()
        if outcome.outcome is None:
            return not values
        schema = operation.outcome_schema_value(outcome.outcome)
        if schema is None:
            return not values
        return OutcomeResultMixin._valid_json_object(schema, values)

    @staticmethod
    def _valid_json_object(
        schema: Mapping[str, object],
        values: Mapping[str, object],
    ) -> bool:
        if not schema:
            return not values
        try:
            schema_value = cast(dict[Any, Any], schema)
            validator_type = validator_for(schema_value)
            validator_type.check_schema(schema_value)
            return validator_type(schema_value).is_valid(cast(Any, values))
        except Exception:
            return False

    @staticmethod
    def _is_external_write(operation: Operation) -> bool:
        return operation.safety_class in {
            SafetyClass.WRITE_EXTERNAL,
            SafetyClass.DESTRUCTIVE,
            SafetyClass.CREDENTIAL,
            SafetyClass.ADMIN,
        }

    def _state_commit_failure_result(
        self,
        *,
        request: OperationRequest,
        attempt: OperationAttempt,
        session: RouteDeckSession,
        result: JournaledExecutionResult,
        tool_phase: OperationPhase,
    ) -> OperationResult:
        failure = self._failure(
            request,
            kind=FailureKind.PERSISTENCE,
            code="state_commit_failed",
            phase="state_commit",
            message="The recorded operation result could not be applied yet.",
            delivery_phase=result.delivery_phase,
        )
        return self._failure_result(
            request=request,
            fingerprint=attempt.request_fingerprint,
            attempt_id=attempt.attempt_id,
            session_version=session.session_version,
            projection_version=session.projection_version,
            disposition=OperationDisposition.FAILED,
            failure=failure,
            phases=(
                *self._supervised_phases(),
                OperationPhase.EXECUTION_CLAIMED,
                OperationPhase.TOOL_STARTED,
                tool_phase,
                OperationPhase.EXECUTION_RESULT_RECORDED,
            ),
            delivery_phase=result.delivery_phase,
            result=result,
        )

    @staticmethod
    def _evidence(
        attempt: OperationAttempt,
        phases: tuple[OperationPhase, ...],
        *,
        result: JournaledExecutionResult | None = None,
        delivery_phase: DeliveryPhase | None = None,
    ) -> OperationEvidence:
        return OperationEvidence(
            source=attempt.source,
            phases=phases,
            attempt_id=attempt.attempt_id,
            request_fingerprint=attempt.request_fingerprint,
            delivery_phase=(
                result.delivery_phase if result is not None else delivery_phase
            ),
            result_id=result.result_id if result is not None else None,
            result_fingerprint=(
                result.result_fingerprint if result is not None else None
            ),
        )

    def _completed_result(
        self,
        request: OperationRequest,
        attempt: OperationAttempt,
        result: JournaledExecutionResult,
        snapshot: SessionSnapshot,
    ) -> OperationResult:
        if result.outcome is None:
            raise RuntimeError("Completed result is missing an outcome")
        return OperationResult(
            disposition=OperationDisposition.COMPLETED,
            session_id=request.session_id,
            request_id=request.request_id,
            operation_id=request.operation_id,
            session_version=snapshot.session_version,
            projection_version=snapshot.projection_version,
            evidence=OperationEvidence(
                source=request.source,
                phases=(
                    *self._supervised_phases(),
                    OperationPhase.EXECUTION_CLAIMED,
                    OperationPhase.TOOL_STARTED,
                    OperationPhase.TOOL_SUCCEEDED,
                    OperationPhase.EXECUTION_RESULT_RECORDED,
                    OperationPhase.STATE_COMMITTED,
                    OperationPhase.COMPLETED,
                ),
                attempt_id=attempt.attempt_id,
                request_fingerprint=attempt.request_fingerprint,
                delivery_phase=result.delivery_phase,
                result_id=result.result_id,
                result_fingerprint=result.result_fingerprint,
            ),
            outcome=result.outcome,
        )

    def _result_from_stored(
        self,
        stored: StoredOperationAttempt,
        *,
        session_id: str,
    ) -> OperationResult | None:
        if (
            stored.disposition is None
            or stored.evidence is None
            or stored.committed_session_version is None
            or stored.committed_projection_version is None
        ):
            return None
        review = None
        if (
            stored.review is not None
            and stored.disposition is OperationDisposition.REQUIRES_REVIEW
        ):
            review = OperationReview(
                id=stored.review.review_id,
                expires_at=stored.review.expires_at,
            )
        outcome = None
        failure = None
        if stored.disposition is not OperationDisposition.PENDING:
            outcome = (
                stored.journaled_result.outcome
                if stored.journaled_result is not None
                else None
            )
            failure = stored.failure or (
                stored.journaled_result.failure
                if stored.journaled_result is not None
                else None
            )
        return OperationResult(
            disposition=stored.disposition,
            session_id=session_id,
            request_id=stored.attempt.request_id,
            operation_id=stored.attempt.operation_id,
            session_version=stored.committed_session_version,
            projection_version=stored.committed_projection_version,
            evidence=stored.evidence,
            review=review,
            outcome=outcome,
            failure=failure,
        )

    def _operation_event(
        self,
        state: RouteDeckSession,
        request: OperationRequest,
        public_state: PublicSessionState,
    ) -> RouteDeckEvent:
        return RouteDeckEvent(
            event_id=self.id_factory("event"),
            cursor=state.event_cursor,
            event_type=RouteDeckEventType.OPERATION_CHANGED,
            session_id=state.session_id,
            session_version=state.session_version,
            projection_version=state.projection_version,
            created_at=self.clock.now(),
            payload=PublicEventPayload(
                node_id=state.current.node_id,
                operation_id=request.operation_id,
                request_id=request.request_id,
                status_code=public_state.status_code,
                failure=public_state.failure,
            ),
        )




__all__ = ["OutcomeResultMixin"]
