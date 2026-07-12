import { RouteDeckContractError } from "./errors";

export interface RouteDeckRetainedRequest<T> {
  readonly request: T;
  readonly fingerprint: string;
}

export function retainRouteDeckRequest<T>(
  request: T,
): RouteDeckRetainedRequest<T> {
  const fingerprint = canonicalJson(request, "$retainedRequest", new WeakSet());
  const retained = JSON.parse(fingerprint) as T;
  return Object.freeze({
    request: deepFreeze(retained),
    fingerprint,
  });
}

function canonicalJson(
  value: unknown,
  path: string,
  ancestors: WeakSet<object>,
): string {
  if (value === null) return "null";
  if (typeof value === "string" || typeof value === "boolean") {
    return JSON.stringify(value);
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) invalid(path, "numbers must be finite");
    return JSON.stringify(value);
  }
  if (typeof value !== "object") {
    invalid(path, "expected JSON-compatible request data");
  }
  if (ancestors.has(value)) invalid(path, "request data must not be cyclic");
  ancestors.add(value);
  try {
    if (Array.isArray(value)) {
      return `[${value
        .map((item, index) => canonicalJson(item, `${path}[${index}]`, ancestors))
        .join(",")}]`;
    }
    const record = value as Record<string, unknown>;
    return `{${Object.keys(record)
      .sort()
      .map(
        (key) =>
          `${JSON.stringify(key)}:${canonicalJson(record[key], `${path}.${key}`, ancestors)}`,
      )
      .join(",")}}`;
  } finally {
    ancestors.delete(value);
  }
}

function deepFreeze<T>(value: T): T {
  if (value !== null && typeof value === "object" && !Object.isFrozen(value)) {
    for (const child of Object.values(value)) deepFreeze(child);
    Object.freeze(value);
  }
  return value;
}

function invalid(path: string, expectation: string): never {
  throw new RouteDeckContractError(path, expectation);
}
