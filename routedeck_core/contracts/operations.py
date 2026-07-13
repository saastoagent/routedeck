from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .effects import SessionEffects
from .failures import RouteDeckFailure
from .projection import FrozenJsonObject


class _FrozenContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SafetyClass(StrEnum):
    NAVIGATION = "navigation"
    STATE_SELECTION = "state_selection"
    DRAFT = "draft"
    READ_EXTERNAL = "read_external"
    WRITE_EXTERNAL = "write_external"
    DESTRUCTIVE = "destructive"
    CREDENTIAL = "credential"
    ADMIN = "admin"


class ReviewPolicy(StrEnum):
    NONE = "none"
    REQUIRED = "required"


class OperationSource(StrEnum):
    SURFACE = "surface"
    AGENT = "agent"
    SYSTEM = "system"
    ROUTE = "route"


class DeliveryPhase(StrEnum):
    NOT_SENT = "not_sent"
    POSSIBLY_SENT = "possibly_sent"
    RESPONSE_RECEIVED = "response_received"


class OperationDisposition(StrEnum):
    COMPLETED = "completed"
    BLOCKED = "blocked"
    NEEDS_INPUT = "needs_input"
    REQUIRES_REVIEW = "requires_review"
    PENDING = "pending"
    FAILED = "failed"
    EXTERNAL_OUTCOME_UNKNOWN = "external_outcome_unknown"


class OperationPhase(StrEnum):
    RECEIVED = "received"
    LEASE_ACQUIRED = "lease_acquired"
    VALIDATED = "validated"
    CONTEXT_REFRESHED = "context_refreshed"
    GUARDS_PASSED = "guards_passed"
    REVIEW_STAGED = "review_staged"
    EXECUTION_CLAIMED = "execution_claimed"
    TOOL_STARTED = "tool_started"
    TOOL_SUCCEEDED = "tool_succeeded"
    TOOL_FAILED = "tool_failed"
    TOOL_OUTCOME_UNKNOWN = "tool_outcome_unknown"
    EXECUTION_RESULT_RECORDED = "execution_result_recorded"
    STATE_COMMITTED = "state_committed"
    COMPLETED = "completed"


class OperationRequest(_FrozenContract):
    session_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    expected_session_version: int = Field(ge=0)
    operation_id: str = Field(min_length=1)
    source: OperationSource
    arguments: FrozenJsonObject = Field(default_factory=lambda: FrozenJsonObject({}))


class OperationOutcome(_FrozenContract):
    outcome: str | None = Field(default=None, min_length=1)
    delivery_phase: DeliveryPhase
    observation: FrozenJsonObject = Field(default_factory=lambda: FrozenJsonObject({}))
    effects: SessionEffects = Field(default_factory=SessionEffects)
    failure: RouteDeckFailure | None = None

    @model_validator(mode="after")
    def _success_or_failure(self) -> OperationOutcome:
        if self.outcome is None and self.failure is None:
            raise ValueError("OperationOutcome requires an outcome or failure")
        if self.outcome is not None and self.failure is not None:
            raise ValueError("OperationOutcome requires outcome or failure, not both")
        if self.outcome is not None and self.delivery_phase is DeliveryPhase.NOT_SENT:
            raise ValueError("successful outcomes cannot be not_sent")
        if self.failure is not None and self.effects.complete_session:
            raise ValueError("session completion requires a successful outcome")
        if (
            self.failure is not None
            and not self.effects.is_empty
            and self.delivery_phase is DeliveryPhase.NOT_SENT
        ):
            raise ValueError("not-sent failures cannot contain session effects")
        return self


class OperationEvidence(_FrozenContract):
    source: OperationSource
    phases: tuple[OperationPhase, ...]
    attempt_id: str = Field(min_length=1)
    request_fingerprint: str = Field(min_length=1)
    delivery_phase: DeliveryPhase | None = None
    result_id: str | None = Field(default=None, min_length=1)
    result_fingerprint: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _ordered_unique_phases(self) -> OperationEvidence:
        if not self.phases:
            raise ValueError("OperationEvidence requires at least one phase")
        if len(self.phases) != len(set(self.phases)):
            raise ValueError("OperationEvidence phases must be unique")
        order = {phase: index for index, phase in enumerate(OperationPhase)}
        indices = tuple(order[phase] for phase in self.phases)
        if indices != tuple(sorted(indices)):
            raise ValueError("OperationEvidence phases must follow lifecycle order")
        return self


class OperationReview(_FrozenContract):
    id: str = Field(min_length=1)
    expires_at: datetime

    @model_validator(mode="after")
    def _aware_expiry(self) -> OperationReview:
        if self.expires_at.tzinfo is None:
            raise ValueError("expires_at must be timezone-aware")
        return self


class OperationResult(_FrozenContract):
    disposition: OperationDisposition
    session_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    session_version: int = Field(ge=0)
    projection_version: int = Field(ge=0)
    evidence: OperationEvidence
    review: OperationReview | None = None
    outcome: str | None = Field(default=None, min_length=1)
    failure: RouteDeckFailure | None = None

    @model_validator(mode="after")
    def _disposition_payload(self) -> OperationResult:
        if self.disposition is OperationDisposition.COMPLETED:
            if (
                self.outcome is None
                or self.failure is not None
                or self.review is not None
            ):
                raise ValueError("completed payload requires only a declared outcome")
        elif self.disposition is OperationDisposition.REQUIRES_REVIEW:
            if (
                self.review is None
                or self.outcome is not None
                or self.failure is not None
            ):
                raise ValueError("requires_review results require only review metadata")
        elif self.disposition in {
            OperationDisposition.BLOCKED,
            OperationDisposition.NEEDS_INPUT,
            OperationDisposition.FAILED,
            OperationDisposition.EXTERNAL_OUTCOME_UNKNOWN,
        }:
            if (
                self.failure is None
                or self.outcome is not None
                or self.review is not None
            ):
                raise ValueError(
                    f"{self.disposition.value} results require only a failure"
                )
        elif self.disposition is OperationDisposition.PENDING:
            if (
                self.outcome is not None
                or self.failure is not None
                or self.review is not None
            ):
                raise ValueError("pending results cannot contain terminal payloads")
        return self


class OperationRef(_FrozenContract):
    id: str = Field(min_length=1)


class ProviderRef(_FrozenContract):
    id: str = Field(min_length=1)


class GuardRef(_FrozenContract):
    id: str = Field(min_length=1)


class ContextProviderSpec(_FrozenContract):
    id: str = Field(min_length=1)
    description: str
    output_schema: FrozenJsonObject = Field(
        default_factory=lambda: FrozenJsonObject({})
    )

    def output_schema_value(self) -> dict[str, object]:
        return self.output_schema.to_dict()

    @property
    def ref(self) -> ProviderRef:
        return ProviderRef(id=self.id)


class EntityProviderSpec(_FrozenContract):
    id: str = Field(min_length=1)
    entity_kind: str = Field(min_length=1)
    description: str
    output_schema: FrozenJsonObject = Field(
        default_factory=lambda: FrozenJsonObject({})
    )

    def output_schema_value(self) -> dict[str, object]:
        return self.output_schema.to_dict()

    @property
    def ref(self) -> ProviderRef:
        return ProviderRef(id=self.id)


class GuardSpec(_FrozenContract):
    id: str = Field(min_length=1)
    description: str

    @property
    def ref(self) -> GuardRef:
        return GuardRef(id=self.id)


class EntityInputSpec(_FrozenContract):
    argument_name: str = Field(min_length=1)
    entity_kind: str = Field(min_length=1)


class OperationSpec(_FrozenContract):
    id: str = Field(min_length=1)
    title: str
    description: str
    input_schema: FrozenJsonObject = Field(default_factory=lambda: FrozenJsonObject({}))
    safety_class: SafetyClass
    review_policy: ReviewPolicy = ReviewPolicy.NONE
    outcomes: tuple[str, ...]
    outcome_schemas: FrozenJsonObject = Field(
        default_factory=lambda: FrozenJsonObject({})
    )
    entity_inputs: tuple[EntityInputSpec, ...] = ()
    provider_refs: tuple[ProviderRef, ...] = ()
    guard_refs: tuple[GuardRef, ...] = ()
    policy_refs: tuple[AgentPolicyRef, ...] = ()
    unknown_recovery_directive: str | None = Field(default=None, min_length=1)
    unknown_recovery_operation_refs: tuple[OperationRef, ...] = ()
    public_metadata: FrozenJsonObject = Field(
        default_factory=lambda: FrozenJsonObject({})
    )

    def input_schema_value(self) -> dict[str, object]:
        return self.input_schema.to_dict()

    def public_metadata_value(self) -> dict[str, object]:
        return self.public_metadata.to_dict()

    def outcome_schema_value(self, outcome: str) -> dict[str, object] | None:
        schema = self.outcome_schemas.to_dict().get(outcome)
        if schema is None:
            return None
        if not isinstance(schema, dict):
            raise TypeError("operation outcome schema must be a JSON object")
        return schema

    @model_validator(mode="after")
    def _unique_entity_inputs(self) -> OperationSpec:
        if not self.outcomes or len(self.outcomes) != len(set(self.outcomes)):
            raise ValueError("operation outcomes must be non-empty and unique")
        _require_valid_json_schema(
            self.input_schema.to_dict(),
            label="operation input_schema",
        )
        schema_outcomes = set(self.outcome_schemas.to_dict())
        if not schema_outcomes <= set(self.outcomes):
            raise ValueError(
                "operation outcome schemas must reference declared outcomes"
            )
        if any(
            not isinstance(schema, dict)
            for schema in self.outcome_schemas.to_dict().values()
        ):
            raise ValueError("operation outcome schemas must be JSON objects")
        for outcome, schema in self.outcome_schemas.to_dict().items():
            if not isinstance(schema, dict):
                continue
            _require_valid_json_schema(
                schema,
                label=f"operation outcome schema {outcome!r}",
            )
        provider_ids = tuple(ref.id for ref in self.provider_refs)
        if len(provider_ids) != len(set(provider_ids)):
            raise ValueError("operation provider refs must be unique")
        guard_ids = tuple(ref.id for ref in self.guard_refs)
        if len(guard_ids) != len(set(guard_ids)):
            raise ValueError("operation guard refs must be unique")
        recovery_operation_ids = tuple(
            ref.id for ref in self.unknown_recovery_operation_refs
        )
        if len(recovery_operation_ids) != len(set(recovery_operation_ids)):
            raise ValueError("operation unknown recovery refs must be unique")
        if self.safety_class is SafetyClass.WRITE_EXTERNAL:
            if self.unknown_recovery_directive is None:
                raise ValueError(
                    "write_external operations require an unknown recovery directive"
                )
        elif (
            self.unknown_recovery_directive is not None
            or self.unknown_recovery_operation_refs
        ):
            raise ValueError(
                "unknown recovery fields are valid only for write_external operations"
            )
        names = tuple(item.argument_name for item in self.entity_inputs)
        if len(names) != len(set(names)):
            raise ValueError("operation entity input argument names must be unique")
        schema = self.input_schema_value()
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            properties = {}
        missing = tuple(name for name in names if name not in properties)
        if missing:
            raise ValueError(
                "operation entity inputs must reference declared schema properties"
            )
        invalid = tuple(
            name
            for name in names
            if not isinstance(properties.get(name), dict)
            or properties[name].get("type") != "string"
        )
        if invalid:
            raise ValueError("operation entity inputs require a string schema property")
        return self

    @property
    def ref(self) -> OperationRef:
        return OperationRef(id=self.id)


ProviderSpec = ContextProviderSpec | EntityProviderSpec


def _require_valid_json_schema(schema: dict[str, object], *, label: str) -> None:
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError:
        raise ValueError(f"{label} must be valid JSON Schema") from None


__all__ = [
    "ContextProviderSpec",
    "DeliveryPhase",
    "EntityInputSpec",
    "EntityProviderSpec",
    "GuardRef",
    "GuardSpec",
    "OperationDisposition",
    "OperationEvidence",
    "OperationOutcome",
    "OperationPhase",
    "OperationRef",
    "OperationRequest",
    "OperationResult",
    "OperationReview",
    "OperationSource",
    "OperationSpec",
    "ProviderRef",
    "ProviderSpec",
    "ReviewPolicy",
    "SafetyClass",
]
from .agent import AgentPolicyRef
