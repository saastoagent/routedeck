from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .conversation import ConversationTurn
from .effects import SessionEffects
from .failures import RouteDeckFailure
from .operations import (
    DeliveryPhase,
    OperationDisposition,
    OperationEvidence,
    OperationSource,
)
from .projection import ClassifiedValue, FrozenJson, PublicEntityHandle
from .projection import FrozenJsonObject


class _FrozenContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=True,
    )


class LocationParameter(_FrozenContract):
    name: str = Field(min_length=1)
    value: str = Field(min_length=1)


class Location(_FrozenContract):
    node_id: str = Field(min_length=1)
    route_params: tuple[LocationParameter, ...] = ()
    entry_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _unique_route_parameters(self) -> Location:
        names = tuple(parameter.name for parameter in self.route_params)
        if len(names) != len(set(names)):
            raise ValueError("Location route parameter names must be unique")
        return self


class PrivateFieldValue(_FrozenContract):
    name: str = Field(min_length=1)
    value: FrozenJson


class PrivateDraft(_FrozenContract):
    form_id: str = Field(min_length=1)
    field_names: tuple[str, ...] = ()
    revision: int = Field(ge=1)
    complete: bool = False

    @model_validator(mode="after")
    def _unique_field_names(self) -> PrivateDraft:
        _require_unique(self.field_names, "private draft field names")
        if any(not name for name in self.field_names):
            raise ValueError("private draft field names must be non-empty")
        return self


class PrivateEntityBinding(_FrozenContract):
    entity_kind: str = Field(min_length=1)
    public_handle: str = Field(min_length=1)
    private_id: str = Field(min_length=1)
    allowed_operation_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _unique_allowed_operations(self) -> PrivateEntityBinding:
        _require_unique(
            self.allowed_operation_ids,
            "entity binding operation IDs",
        )
        return self


class ResumeCapabilityBinding(_FrozenContract):
    handle: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    node_id: str = Field(min_length=1)
    expires_at: datetime
    route_params: tuple[LocationParameter, ...] = ()

    @model_validator(mode="after")
    def _aware_expiry(self) -> ResumeCapabilityBinding:
        if self.expires_at.tzinfo is None:
            raise ValueError("expires_at must be timezone-aware")
        _require_unique(
            tuple(parameter.name for parameter in self.route_params),
            "resume capability route parameter names",
        )
        return self


class PrivateConfiguration(_FrozenContract):
    namespace: str = Field(min_length=1)
    fields: tuple[PrivateFieldValue, ...]

    @model_validator(mode="after")
    def _unique_fields(self) -> PrivateConfiguration:
        _require_unique(
            tuple(field.name for field in self.fields),
            "private configuration field names",
        )
        return self


class PrivateSessionState(_FrozenContract):
    drafts: tuple[PrivateDraft, ...] = ()
    entity_bindings: tuple[PrivateEntityBinding, ...] = ()
    resume_capabilities: tuple[ResumeCapabilityBinding, ...] = ()
    configurations: tuple[PrivateConfiguration, ...] = ()

    @model_validator(mode="after")
    def _unique_private_state_keys(self) -> PrivateSessionState:
        _require_unique(
            tuple(draft.form_id for draft in self.drafts),
            "private draft form IDs",
        )
        _require_unique(
            tuple(binding.public_handle for binding in self.entity_bindings),
            "private entity public handles",
        )
        _require_unique(
            tuple(capability.handle for capability in self.resume_capabilities),
            "resume capability handles",
        )
        _require_unique(
            tuple(configuration.namespace for configuration in self.configurations),
            "private configuration namespaces",
        )
        return self


class PublicSurfaceState(_FrozenContract):
    surface_id: str = Field(min_length=1)
    values: tuple[ClassifiedValue, ...] = ()

    @model_validator(mode="after")
    def _unique_values(self) -> PublicSurfaceState:
        _require_unique(
            tuple(value.name for value in self.values),
            "public surface value names",
        )
        return self


class PublicSessionState(_FrozenContract):
    entity_handles: tuple[PublicEntityHandle, ...] = ()
    surface_state: tuple[PublicSurfaceState, ...] = ()
    status_code: str = "ready"
    status_message: str | None = None
    failure: RouteDeckFailure | None = None
    disabled_operation_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _unique_public_state_keys(self) -> PublicSessionState:
        _require_unique(
            tuple(entity.handle for entity in self.entity_handles),
            "public entity handles",
        )
        _require_unique(
            tuple(surface.surface_id for surface in self.surface_state),
            "public surface IDs",
        )
        _require_unique(self.disabled_operation_ids, "disabled operation IDs")
        return self


class OperationAttemptStatus(StrEnum):
    RECEIVED = "received"
    REVIEW_PENDING = "review_pending"
    EXECUTION_CLAIMED = "execution_claimed"
    TOOL_STARTED = "tool_started"
    RESULT_RECORDED = "result_recorded"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    EXTERNAL_OUTCOME_UNKNOWN = "external_outcome_unknown"


class AttemptTerminalState(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    REVIEW_REJECTED = "review_rejected"
    EXTERNAL_OUTCOME_UNKNOWN = "external_outcome_unknown"


class ReviewResolution(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    STALE = "stale"
    EXPIRED = "expired"


class OperationArgument(_FrozenContract):
    name: str = Field(min_length=1)
    value: FrozenJson


class OperationAttempt(_FrozenContract):
    attempt_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    request_fingerprint: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    source: OperationSource
    expected_session_version: int = Field(ge=0)
    arguments: tuple[OperationArgument, ...] = ()
    parent_turn_id: str | None = None
    resumed_review_id: str | None = None
    context_fingerprint: str | None = Field(default=None, min_length=1)
    status: OperationAttemptStatus = OperationAttemptStatus.RECEIVED
    terminal: AttemptTerminalState | None = None
    failure: RouteDeckFailure | None = None

    @model_validator(mode="after")
    def _unique_argument_names(self) -> OperationAttempt:
        _require_unique(
            tuple(argument.name for argument in self.arguments),
            "operation argument names",
        )
        return self


class PendingReview(_FrozenContract):
    review_id: str = Field(min_length=1)
    attempt: OperationAttempt
    operation_spec_version: str = Field(min_length=1)
    proposal_fingerprint: str = Field(min_length=1)
    projection_version: int = Field(ge=0)
    authoritative_context_fingerprint: str = Field(min_length=1)
    expires_at: datetime
    resolution: ReviewResolution = ReviewResolution.PENDING
    resolved_request_id: str | None = None

    @model_validator(mode="after")
    def _aware_expiry(self) -> PendingReview:
        if self.expires_at.tzinfo is None:
            raise ValueError("expires_at must be timezone-aware")
        return self


class JournaledExecutionResult(_FrozenContract):
    result_id: str = Field(min_length=1)
    attempt_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    outcome: str | None = Field(default=None, min_length=1)
    delivery_phase: DeliveryPhase
    result_fingerprint: str = Field(min_length=1)
    observation: FrozenJsonObject = Field(default_factory=lambda: FrozenJsonObject({}))
    effects: SessionEffects = Field(default_factory=SessionEffects)
    failure: RouteDeckFailure | None = None

    @model_validator(mode="after")
    def _success_or_failure(self) -> JournaledExecutionResult:
        if self.outcome is None and self.failure is None:
            raise ValueError("journaled results require an outcome or failure")
        if self.outcome is not None and self.failure is not None:
            raise ValueError("journaled results require outcome or failure, not both")
        if self.outcome is not None and self.delivery_phase is DeliveryPhase.NOT_SENT:
            raise ValueError("successful outcomes cannot be not_sent")
        if self.failure is not None and not self.effects.is_empty:
            raise ValueError("failed journal results cannot contain session effects")
        return self


class StoredOperationAttempt(_FrozenContract):
    attempt: OperationAttempt
    review: PendingReview | None = None
    journaled_result: JournaledExecutionResult | None = None
    disposition: OperationDisposition | None = None
    evidence: OperationEvidence | None = None
    committed_session_version: int | None = Field(default=None, ge=0)
    committed_projection_version: int | None = Field(default=None, ge=0)
    failure: RouteDeckFailure | None = None

    @model_validator(mode="after")
    def _matching_attempt_identity(self) -> StoredOperationAttempt:
        if self.review is not None and (
            self.review.attempt.attempt_id != self.attempt.attempt_id
            and self.attempt.resumed_review_id != self.review.review_id
        ):
            raise ValueError("stored review must belong to its operation attempt")
        if self.journaled_result is not None and (
            self.journaled_result.attempt_id != self.attempt.attempt_id
        ):
            raise ValueError("journaled result must belong to its operation attempt")
        return self


class OperationState(_FrozenContract):
    active_attempt: OperationAttempt | None = None
    pending_review: PendingReview | None = None
    journaled_result: JournaledExecutionResult | None = None


class RouteDeckSession(_FrozenContract):
    session_id: str = Field(min_length=1)
    schema_version: int = Field(ge=1)
    navgraph_version: str = Field(min_length=1)
    session_version: int = Field(ge=0)
    projection_version: int = Field(ge=0)
    event_cursor: int = Field(ge=0)
    next_history_entry_id: int = Field(ge=1)
    current: Location
    back_stack: tuple[Location, ...] = ()
    forward_stack: tuple[Location, ...] = ()
    conversation: tuple[ConversationTurn, ...] = ()
    private_state: PrivateSessionState
    public_state: PublicSessionState = Field(default_factory=PublicSessionState)
    operation: OperationState | None = None

    @model_validator(mode="after")
    def _canonical_session_invariants(self) -> RouteDeckSession:
        _require_unique(
            tuple(turn.turn_id for turn in self.conversation),
            "conversation turn IDs",
        )
        if any(
            capability.session_id != self.session_id
            for capability in self.private_state.resume_capabilities
        ):
            raise ValueError("resume capabilities must belong to their session")
        if self.projection_version > self.session_version:
            raise ValueError("projection_version cannot exceed session_version")
        locations = (*self.back_stack, self.current, *self.forward_stack)
        entry_ids = tuple(location.entry_id for location in locations)
        if any(entry_id is None for entry_id in entry_ids):
            raise ValueError("canonical navigation locations require history entry IDs")
        if len(entry_ids) != len(set(entry_ids)):
            raise ValueError("canonical history entry IDs must be unique")
        if entry_ids and self.next_history_entry_id <= max(
            entry_id for entry_id in entry_ids if entry_id is not None
        ):
            raise ValueError(
                "next_history_entry_id must exceed every canonical history entry ID"
            )
        return self


class SessionSnapshot(_FrozenContract):
    state: RouteDeckSession

    @property
    def session_id(self) -> str:
        return self.state.session_id

    @property
    def session_version(self) -> int:
        return self.state.session_version

    @property
    def projection_version(self) -> int:
        return self.state.projection_version

    @property
    def event_cursor(self) -> int:
        return self.state.event_cursor


def _require_unique(values: tuple[str, ...], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must be unique")


__all__ = [
    "AttemptTerminalState",
    "JournaledExecutionResult",
    "Location",
    "LocationParameter",
    "OperationArgument",
    "OperationAttempt",
    "OperationAttemptStatus",
    "OperationState",
    "PendingReview",
    "PrivateConfiguration",
    "PrivateDraft",
    "PrivateEntityBinding",
    "PrivateFieldValue",
    "PrivateSessionState",
    "PublicSessionState",
    "PublicSurfaceState",
    "ResumeCapabilityBinding",
    "ReviewResolution",
    "RouteDeckSession",
    "SessionSnapshot",
    "StoredOperationAttempt",
]
