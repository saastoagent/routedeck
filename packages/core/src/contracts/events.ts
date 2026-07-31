import type {
  PublicEventPayload,
  PublicRouteDeckEvent as GeneratedRouteDeckEvent,
  RouteDeckEventType,
} from "./generated";
import { generatedObjectDescriptors } from "./generatedRuntime";
import strictJsonDecoders from "./json";
import operationDecoders from "./operations";
import type {
  RouteDeckPublicEntityHandle,
  RouteDeckPublicValue,
} from "./projection";
import projectionDecoders from "./projection";

const {
  decodeArray,
  decodeNullableString,
  expectEnum,
  expectInteger,
  expectIsoDate,
  expectRecord,
  expectString,
} = strictJsonDecoders;
const { decodeFailure } = operationDecoders;
const { decodeEntity, decodePublicValue } = projectionDecoders;

export interface RouteDeckEventPayload
  extends Omit<PublicEventPayload, "details" | "entity_handles"> {
  details: RouteDeckPublicValue[];
  entity_handles: RouteDeckPublicEntityHandle[];
}

export interface RouteDeckEvent
  extends Omit<
    GeneratedRouteDeckEvent,
    "payload" | "projection_version" | "session_id"
  > {
  payload: RouteDeckEventPayload;
  projection_version: number | null;
}

const EVENT_TYPES = new Set<RouteDeckEventType>([
  "session_created",
  "projection_changed",
  "navigation_changed",
  "operation_changed",
  "private_form_changed",
  "turn_started",
  "turn_finalized",
  "turn_interrupted",
]);

export function decodeEvent(value: unknown): RouteDeckEvent {
  const record = expectRecord(
    value,
    "$event",
    generatedObjectDescriptors.PublicRouteDeckEvent,
  );
  const eventType = expectEnum(
    record.event_type,
    "$event.event_type",
    EVENT_TYPES,
  );
  const payloadRecord = expectRecord(
    record.payload,
    "$event.payload",
    generatedObjectDescriptors.PublicEventPayload,
  );
  return {
    created_at: expectIsoDate(record.created_at, "$event.created_at"),
    cursor: expectInteger(record.cursor, "$event.cursor", 1),
    event_id: expectString(record.event_id, "$event.event_id"),
    event_type: eventType,
    payload: {
      node_id: decodeNullableString(
        payloadRecord.node_id === undefined ? null : payloadRecord.node_id,
        "$event.payload.node_id",
      ),
      operation_id: decodeNullableString(
        payloadRecord.operation_id === undefined ? null : payloadRecord.operation_id,
        "$event.payload.operation_id",
      ),
      request_id: decodeNullableString(
        payloadRecord.request_id === undefined ? null : payloadRecord.request_id,
        "$event.payload.request_id",
      ),
      status_code: decodeNullableString(
        payloadRecord.status_code === undefined ? null : payloadRecord.status_code,
        "$event.payload.status_code",
      ),
      entity_handles: decodeArray(
        payloadRecord.entity_handles === undefined ? [] : payloadRecord.entity_handles,
        "$event.payload.entity_handles",
        decodeEntity,
      ),
      details: decodeArray(
        payloadRecord.details === undefined ? [] : payloadRecord.details,
        "$event.payload.details",
        decodePublicValue,
      ),
      failure:
        payloadRecord.failure === undefined || payloadRecord.failure === null
          ? null
          : decodeFailure(payloadRecord.failure, "$event.payload.failure"),
    },
    projection_version:
      record.projection_version === undefined || record.projection_version === null
        ? null
        : expectInteger(record.projection_version, "$event.projection_version", 0),
    session_version: expectInteger(
      record.session_version,
      "$event.session_version",
      0,
    ),
  };
}
