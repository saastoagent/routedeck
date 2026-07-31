import type { PrivateFormWriteRequest } from "./generated";
import { generatedObjectDescriptors } from "./generatedRuntime";
import type { JsonObject } from "./json";
import strictJsonDecoders from "./json";

const {
  expectBoolean,
  expectInteger,
  expectJsonObject,
  expectRecord,
  expectString,
} = strictJsonDecoders;

export type RouteDeckPrivateFormWriteRequest = PrivateFormWriteRequest;

export interface RouteDeckPrivateFormSnapshot {
  form_id: string;
  revision: number;
  complete: boolean;
  session_version: number;
  value: JsonObject;
}

export interface RouteDeckPrivateFormSaved {
  form_id: string;
  revision: number;
  complete: boolean;
  session_version: number;
  projection_version: number;
}

export function decodePrivateFormSnapshot(
  value: unknown,
): RouteDeckPrivateFormSnapshot {
  const record = expectRecord(
    value,
    "$privateForm",
    generatedObjectDescriptors.PrivateFormSnapshot,
  );
  return {
    form_id: expectString(record.form_id, "$privateForm.form_id"),
    revision: expectInteger(record.revision, "$privateForm.revision", 0),
    complete: expectBoolean(record.complete, "$privateForm.complete"),
    session_version: expectInteger(
      record.session_version,
      "$privateForm.session_version",
      0,
    ),
    value: expectJsonObject(record.value, "$privateForm.value"),
  };
}

export function decodePrivateFormSaved(value: unknown): RouteDeckPrivateFormSaved {
  const record = expectRecord(
    value,
    "$privateFormSaved",
    generatedObjectDescriptors.PrivateFormSaved,
  );
  return {
    form_id: expectString(record.form_id, "$privateFormSaved.form_id"),
    revision: expectInteger(record.revision, "$privateFormSaved.revision", 1),
    complete: expectBoolean(record.complete, "$privateFormSaved.complete"),
    session_version: expectInteger(
      record.session_version,
      "$privateFormSaved.session_version",
      0,
    ),
    projection_version: expectInteger(
      record.projection_version,
      "$privateFormSaved.projection_version",
      0,
    ),
  };
}
