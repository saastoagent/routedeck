import type {
  DispatchRequest,
  FailureKind,
  OperationDisposition,
  OperationPhase,
  PublicOperationResult,
  OperationSource,
  ReviewRequest,
  RouteDeckFailure,
} from "./generated";
import { generatedObjectDescriptors } from "./generatedRuntime";
import strictJsonDecoders from "./json";

const {
  decodeArray,
  decodeNullableString,
  expectEnum,
  expectInteger,
  expectIsoDate,
  expectOneOf,
  expectRecord,
  expectString,
} = strictJsonDecoders;

export type RouteDeckDispatchRequest = DispatchRequest;
export type RouteDeckReviewRequest = ReviewRequest;
export type RouteDeckDispatchResult = PublicOperationResult;

export interface RouteDeckFailureEnvelope {
  failure: RouteDeckFailure;
}

const FAILURE_KINDS = new Set<FailureKind>([
  "contract",
  "state_conflict",
  "context_provider",
  "guard",
  "review",
  "transport",
  "provider_protocol",
  "business",
  "persistence",
  "external_outcome_unknown",
  "internal",
]);
const DISPOSITIONS = new Set<OperationDisposition>([
  "completed",
  "blocked",
  "needs_input",
  "requires_review",
  "pending",
  "failed",
  "external_outcome_unknown",
]);
const OPERATION_SOURCES = new Set<OperationSource>([
  "surface",
  "agent",
  "system",
  "route",
]);
const OPERATION_PHASES = new Set<OperationPhase>([
  "received",
  "lease_acquired",
  "validated",
  "context_refreshed",
  "guards_passed",
  "review_staged",
  "execution_claimed",
  "tool_started",
  "tool_succeeded",
  "tool_failed",
  "tool_outcome_unknown",
  "execution_result_recorded",
  "state_committed",
  "completed",
]);

export function decodeDispatchResult(value: unknown): RouteDeckDispatchResult {
  const record = expectRecord(
    value,
    "$result",
    generatedObjectDescriptors.PublicOperationResult,
  );
  const evidence = expectRecord(
    record.evidence,
    "$result.evidence",
    generatedObjectDescriptors.OperationEvidence,
  );
  return {
    disposition: expectEnum(
      record.disposition,
      "$result.disposition",
      DISPOSITIONS,
    ),
    operation_id: expectString(record.operation_id, "$result.operation_id"),
    request_id: expectString(record.request_id, "$result.request_id"),
    session_version: expectInteger(
      record.session_version,
      "$result.session_version",
      0,
    ),
    projection_version: expectInteger(
      record.projection_version,
      "$result.projection_version",
      0,
    ),
    evidence: {
      source: expectEnum(evidence.source, "$result.evidence.source", OPERATION_SOURCES),
      phases: decodeArray(
        evidence.phases,
        "$result.evidence.phases",
        (item, itemPath) => expectEnum(item, itemPath, OPERATION_PHASES),
      ),
      attempt_id: expectString(evidence.attempt_id, "$result.evidence.attempt_id"),
      request_fingerprint: expectString(
        evidence.request_fingerprint,
        "$result.evidence.request_fingerprint",
      ),
      delivery_phase:
        evidence.delivery_phase === undefined || evidence.delivery_phase === null
          ? null
          : expectOneOf(
              evidence.delivery_phase,
              "$result.evidence.delivery_phase",
              ["not_sent", "possibly_sent", "response_received"] as const,
            ),
      result_id: decodeNullableString(
        evidence.result_id === undefined ? null : evidence.result_id,
        "$result.evidence.result_id",
      ),
      result_fingerprint: decodeNullableString(
        evidence.result_fingerprint === undefined
          ? null
          : evidence.result_fingerprint,
        "$result.evidence.result_fingerprint",
      ),
    },
    review:
      record.review === undefined || record.review === null
        ? null
        : decodeReview(record.review, "$result.review"),
    outcome: decodeNullableString(
      record.outcome === undefined ? null : record.outcome,
      "$result.outcome",
    ),
    failure:
      record.failure === undefined || record.failure === null
        ? null
        : decodeFailure(record.failure, "$result.failure"),
  };
}

export function decodeFailureEnvelope(value: unknown): RouteDeckFailureEnvelope {
  const record = expectRecord(
    value,
    "$error",
    generatedObjectDescriptors.FailureEnvelope,
  );
  return { failure: decodeFailure(record.failure, "$error.failure") };
}

function decodeReview(
  value: unknown,
  path: string,
): NonNullable<RouteDeckDispatchResult["review"]> {
  const record = expectRecord(
    value,
    path,
    generatedObjectDescriptors.OperationReview,
  );
  return {
    id: expectString(record.id, `${path}.id`),
    expires_at: expectIsoDate(record.expires_at, `${path}.expires_at`),
  };
}

function decodeFailure(value: unknown, path: string): RouteDeckFailure {
  const record = expectRecord(
    value,
    path,
    generatedObjectDescriptors.RouteDeckFailure,
  );
  const details = expectRecord(
    record.safe_details === undefined ? {} : record.safe_details,
    `${path}.safe_details`,
    generatedObjectDescriptors.FailureSafeDetails,
  );
  return {
    kind: expectEnum(record.kind, `${path}.kind`, FAILURE_KINDS),
    code: expectString(record.code, `${path}.code`),
    phase: expectString(record.phase, `${path}.phase`),
    correlation_id: expectString(record.correlation_id, `${path}.correlation_id`),
    operation_id: decodeNullableString(
      record.operation_id === undefined ? null : record.operation_id,
      `${path}.operation_id`,
    ),
    request_id: decodeNullableString(
      record.request_id === undefined ? null : record.request_id,
      `${path}.request_id`,
    ),
    public_message: expectString(record.public_message, `${path}.public_message`, true),
    recovery_directive: decodeNullableString(
      record.recovery_directive === undefined ? null : record.recovery_directive,
      `${path}.recovery_directive`,
    ),
    safe_details: {
      affected_capability: decodeNullableString(
        details.affected_capability === undefined
          ? null
          : details.affected_capability,
        `${path}.safe_details.affected_capability`,
      ),
      provider: decodeNullableString(
        details.provider === undefined ? null : details.provider,
        `${path}.safe_details.provider`,
      ),
      provider_code: decodeNullableString(
        details.provider_code === undefined ? null : details.provider_code,
        `${path}.safe_details.provider_code`,
      ),
      http_status:
        details.http_status === undefined || details.http_status === null
          ? null
          : expectInteger(details.http_status, `${path}.safe_details.http_status`, 100),
      delivery_phase:
        details.delivery_phase === undefined || details.delivery_phase === null
          ? null
          : expectOneOf(
              details.delivery_phase,
              `${path}.safe_details.delivery_phase`,
              ["not_sent", "possibly_sent", "response_received"] as const,
            ),
    },
  };
}

const operationDecoders = Object.freeze({ decodeFailure });

export default operationDecoders;
