import {
  decodeFailureEnvelope,
  type JsonValue,
} from "../contracts/decode";
import {
  RouteDeckContractError,
  RouteDeckHttpError,
  RouteDeckOutcomeUnknownError,
  RouteDeckResponseContractError,
  RouteDeckTransportError,
} from "./errors";

export type RouteDeckFetch = (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<Response>;

export interface RouteDeckHttpResponse {
  status: number;
  ok: boolean;
  value: JsonValue;
  headers: Headers;
}

export interface RouteDeckHttpTransport {
  readonly baseUrl: string;
  readonly fetch: RouteDeckFetch;
  request(
    path: string,
    options?: {
      method?: "GET" | "POST" | "PUT";
      body?: unknown;
      signal?: AbortSignal;
      cache?: RequestCache;
    },
  ): Promise<RouteDeckHttpResponse>;
}

export async function executeRouteDeckMutation<T>(options: {
  http: RouteDeckHttpTransport;
  path: string;
  requestId: string;
  method: "POST" | "PUT";
  body: unknown;
  cache?: RequestCache;
  decode(response: RouteDeckHttpResponse): T;
  decodeClientError?(response: RouteDeckHttpResponse): T;
}): Promise<T> {
  let response: RouteDeckHttpResponse;
  try {
    response = await options.http.request(options.path, {
      method: options.method,
      body: options.body,
      ...(options.cache === undefined ? {} : { cache: options.cache }),
    });
  } catch (error) {
    if (
      error instanceof RouteDeckTransportError ||
      error instanceof RouteDeckResponseContractError
    ) {
      throw new RouteDeckOutcomeUnknownError(
        options.requestId,
        "The RouteDeck mutation response was lost; its outcome is unknown.",
        { cause: error },
      );
    }
    throw error;
  }
  let successful: RouteDeckHttpResponse;
  try {
    successful = requireSuccessfulResponse(response);
  } catch (error) {
    if (
      error instanceof RouteDeckHttpError &&
      response.status >= 500 &&
      response.status <= 599
    ) {
      if (options.decodeClientError !== undefined) {
        try {
          return requireMatchingMutationResponse(
            options.decodeClientError(response),
            options.requestId,
          );
        } catch (decodeError) {
          if (!(decodeError instanceof RouteDeckContractError)) throw decodeError;
        }
      }
      throw new RouteDeckOutcomeUnknownError(
        options.requestId,
        "The RouteDeck mutation returned a server failure after delivery; its outcome is unknown.",
        { cause: error },
      );
    }
    if (
      error instanceof RouteDeckHttpError &&
      response.status >= 400 &&
      response.status <= 499 &&
      options.decodeClientError !== undefined
    ) {
      try {
        return options.decodeClientError(response);
      } catch (decodeError) {
        if (!(decodeError instanceof RouteDeckContractError)) throw decodeError;
      }
    }
    throw error;
  }
  try {
    return options.decode(successful);
  } catch (error) {
    if (error instanceof RouteDeckContractError) {
      throw new RouteDeckOutcomeUnknownError(
        options.requestId,
        "The RouteDeck mutation returned an invalid success response; its outcome is unknown.",
        { cause: error },
      );
    }
    throw error;
  }
}

function requireMatchingMutationResponse<T>(value: T, requestId: string): T {
  if (
    typeof value !== "object" ||
    value === null ||
    !("request_id" in value) ||
    value.request_id !== requestId
  ) {
    throw new RouteDeckContractError(
      "$mutation.response.request_id",
      "must match the mutation request id",
    );
  }
  return value;
}

export function createRouteDeckHttpTransport(options: {
  baseUrl: string;
  fetch?: RouteDeckFetch;
  credentials?: RequestCredentials;
}): RouteDeckHttpTransport {
  const baseUrl = normalizeBaseUrl(options.baseUrl);
  const fetchImplementation = options.fetch ?? globalThis.fetch?.bind(globalThis);
  if (!fetchImplementation) {
    throw new RouteDeckHttpError(
      0,
      null,
      "A fetch implementation is required for the RouteDeck client.",
    );
  }
  const credentials = options.credentials ?? "same-origin";
  return {
    baseUrl,
    fetch: fetchImplementation,
    async request(path, request = {}) {
      if (!path.startsWith("/")) {
        throw new RouteDeckContractError("$http.path", "must start with /");
      }
      const headers = new Headers({ Accept: "application/json" });
      let body: string | undefined;
      if (request.body !== undefined) {
        headers.set("Content-Type", "application/json");
        body = JSON.stringify(assertJson(request.body, "$http.request.body"));
      }
      let response: Response;
      try {
        response = await fetchImplementation(`${baseUrl}${path}`, {
          method: request.method ?? "GET",
          headers,
          credentials,
          ...(body === undefined ? {} : { body }),
          ...(request.signal === undefined ? {} : { signal: request.signal }),
          ...(request.cache === undefined ? {} : { cache: request.cache }),
        });
      } catch (error) {
        if (request.signal?.aborted) throw error;
        throw new RouteDeckTransportError(
          "request",
          "The RouteDeck HTTP request did not receive a response.",
          { cause: error },
        );
      }
      let responseBody: string;
      try {
        responseBody = await response.text();
      } catch (error) {
        if (request.signal?.aborted) throw error;
        throw new RouteDeckTransportError(
          "response",
          "The RouteDeck HTTP response ended before its body was received.",
          { cause: error },
        );
      }
      let parsed: unknown;
      try {
        parsed = JSON.parse(responseBody);
      } catch (error) {
        throw new RouteDeckResponseContractError(
          "$http.response",
          "expected a JSON response body",
          { cause: error },
        );
      }
      let value: JsonValue;
      try {
        value = assertJson(parsed, "$http.response");
      } catch (error) {
        if (!(error instanceof RouteDeckContractError)) throw error;
        throw new RouteDeckResponseContractError(
          error.path,
          "expected a JSON-compatible response body",
          { cause: error },
        );
      }
      return {
        status: response.status,
        ok: response.ok,
        value,
        headers: response.headers,
      };
    },
  };
}

export function requireSuccessfulResponse(
  response: RouteDeckHttpResponse,
): RouteDeckHttpResponse {
  if (response.ok) return response;
  let failure = null;
  try {
    failure = decodeFailureEnvelope(response.value).failure;
  } catch (error) {
    if (!(error instanceof RouteDeckContractError)) throw error;
  }
  throw new RouteDeckHttpError(
    response.status,
    failure,
    failure?.public_message ?? `RouteDeck HTTP request failed with ${response.status}.`,
  );
}

export function requireNoStore(headers: Headers, path: string): void {
  const cacheControl = headers.get("cache-control");
  const directives = cacheControl
    ?.split(",")
    .map((directive) => directive.trim().toLowerCase());
  if (!directives?.includes("no-store")) {
    throw new RouteDeckContractError(
      path,
      "private-form responses must declare Cache-Control: no-store",
    );
  }
}

function normalizeBaseUrl(value: string): string {
  if (!value || value.endsWith("/")) {
    throw new RouteDeckContractError(
      "$http.baseUrl",
      "must be non-empty and omit the trailing slash",
    );
  }
  return value;
}

function assertJson(value: unknown, path: string): JsonValue {
  if (value === null || typeof value === "string" || typeof value === "boolean") {
    return value;
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) {
      throw new RouteDeckContractError(path, "JSON numbers must be finite");
    }
    return value;
  }
  if (Array.isArray(value)) {
    return value.map((item, index) => assertJson(item, `${path}[${index}]`));
  }
  if (typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([key, item]) => [
        key,
        assertJson(item, `${path}.${key}`),
      ]),
    );
  }
  throw new RouteDeckContractError(path, "expected JSON-compatible data");
}
