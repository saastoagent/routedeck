import { RouteDeckContractError } from "../client/errors";

export type JsonPrimitive = string | number | boolean | null;
export type JsonValue =
  | JsonPrimitive
  | JsonValue[]
  | { [key: string]: JsonValue };
export type JsonObject = { [key: string]: JsonValue };

function expectRecord(
  value: unknown,
  path: string,
  required: readonly string[],
  optional: readonly string[] = [],
): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    fail(path, "expected an object");
  }
  const record = value as Record<string, unknown>;
  for (const key of required) {
    if (!(key in record)) fail(`${path}.${key}`, "is required");
  }
  const allowed = new Set([...required, ...optional]);
  for (const key of Object.keys(record)) {
    if (!allowed.has(key)) fail(`${path}.${key}`, "is not declared by the contract");
  }
  return record;
}

function expectRecordMap(value: unknown, path: string): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    fail(path, "expected an object map");
  }
  return value as Record<string, unknown>;
}

function expectString(value: unknown, path: string, allowEmpty = false): string {
  if (typeof value !== "string" || (!allowEmpty && value.length === 0)) {
    fail(path, allowEmpty ? "expected a string" : "expected a non-empty string");
  }
  return value;
}

function expectBoolean(value: unknown, path: string): boolean {
  if (typeof value !== "boolean") fail(path, "expected a boolean");
  return value;
}

function expectInteger(value: unknown, path: string, minimum: number): number {
  if (!Number.isInteger(value) || (value as number) < minimum) {
    fail(path, `expected an integer >= ${minimum}`);
  }
  return value as number;
}

function expectIsoDate(value: unknown, path: string): string {
  const text = expectString(value, path);
  if (Number.isNaN(Date.parse(text))) fail(path, "expected an ISO date-time string");
  return text;
}

function decodeNullableString(value: unknown, path: string): string | null {
  return value === null ? null : expectString(value, path);
}

function decodeArray<T>(
  value: unknown,
  path: string,
  decode: (item: unknown, path: string) => T,
): T[] {
  if (!Array.isArray(value)) fail(path, "expected an array");
  return value.map((item, index) => decode(item, `${path}[${index}]`));
}

function decodeStringArray(value: unknown, path: string): string[] {
  return decodeArray(value, path, (item, itemPath) => expectString(item, itemPath));
}

function decodeJsonObjectArray(value: unknown, path: string): JsonObject[] {
  return decodeArray(value, path, expectJsonObject);
}

function expectJsonObject(value: unknown, path: string): JsonObject {
  const json = expectJson(value, path);
  if (json === null || Array.isArray(json) || typeof json !== "object") {
    fail(path, "expected a JSON object");
  }
  return json as JsonObject;
}

function expectJson(value: unknown, path: string): JsonValue {
  if (value === null || typeof value === "string" || typeof value === "boolean") {
    return value;
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) fail(path, "JSON numbers must be finite");
    return value;
  }
  if (Array.isArray(value)) {
    return value.map((item, index) => expectJson(item, `${path}[${index}]`));
  }
  if (typeof value === "object") {
    const output: JsonObject = {};
    for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
      output[key] = expectJson(item, `${path}.${key}`);
    }
    return output;
  }
  fail(path, "expected JSON-compatible data");
}

function expectEnum<T extends string>(
  value: unknown,
  path: string,
  values: ReadonlySet<T>,
): T {
  const candidate = expectString(value, path) as T;
  if (!values.has(candidate)) fail(path, "contains an unknown enum value");
  return candidate;
}

function expectOneOf<const T extends readonly string[]>(
  value: unknown,
  path: string,
  values: T,
): T[number] {
  const candidate = expectString(value, path);
  if (!(values as readonly string[]).includes(candidate)) {
    fail(path, `expected one of ${values.join(", ")}`);
  }
  return candidate as T[number];
}

function fail(path: string, expectation: string): never {
  throw new RouteDeckContractError(path, expectation);
}

const strictJsonDecoders = Object.freeze({
  decodeArray,
  decodeJsonObjectArray,
  decodeNullableString,
  decodeStringArray,
  expectBoolean,
  expectEnum,
  expectInteger,
  expectIsoDate,
  expectJson,
  expectJsonObject,
  expectOneOf,
  expectRecord,
  expectRecordMap,
  expectString,
  fail,
});

export default strictJsonDecoders;
