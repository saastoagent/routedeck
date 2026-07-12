import {
  decodeDispatchResult,
  decodeFrontendContractEnvelope,
  decodeInspection,
  decodeSessionEnvelope,
  type RouteDeckDispatchRequest,
  type RouteDeckDispatchResult,
  type RouteDeckInspection,
  type RouteDeckProjection,
  type RouteDeckReviewRequest,
} from "../contracts/decode";
import type { FrontendContract } from "../contracts/generated";
import {
  createRouteDeckHttpTransport,
  executeRouteDeckMutation,
  requireSuccessfulResponse,
  type RouteDeckFetch,
  type RouteDeckHttpResponse,
  type RouteDeckHttpTransport,
} from "./http";
import {
  connectRouteDeckEvents,
  type RouteDeckEventConnection,
  type RouteDeckEventStreamOptions,
} from "./sse";
import {
  createPrivateFormClient,
  type RouteDeckPrivateFormClient,
} from "../private-forms/client";
import {
  RouteDeckContractError,
} from "./errors";

export interface RouteDeckClient {
  getFrontendContract(): Promise<FrontendContract>;
  createSession(request: RouteDeckSessionCreateRequest): Promise<RouteDeckProjection>;
  getSession(): Promise<RouteDeckProjection>;
  navigate(request: RouteDeckNavigationRequest): Promise<RouteDeckProjection>;
  dispatch(request: RouteDeckDispatchRequest): Promise<RouteDeckDispatchResult>;
  acceptReview(
    reviewId: string,
    request: RouteDeckReviewRequest,
  ): Promise<RouteDeckDispatchResult>;
  rejectReview(
    reviewId: string,
    request: RouteDeckReviewRequest,
  ): Promise<RouteDeckDispatchResult>;
  inspect(): Promise<RouteDeckInspection>;
  connectEvents(
    options: Omit<RouteDeckEventStreamOptions, "url" | "fetch" | "credentials">,
  ): RouteDeckEventConnection;
  readonly privateForms: RouteDeckPrivateFormClient;
}

export interface RouteDeckSessionCreateRequest {
  request_id: string;
}

export type RouteDeckNavigationIntent =
  | { kind: "open_path"; path: string }
  | { kind: "back" }
  | { kind: "forward" }
  | { kind: "cancel" }
  | {
      kind: "restore_history_entry";
      history_entry_id: number;
      path: string;
    };

export interface RouteDeckNavigationRequest {
  request_id: string;
  expected_session_version: number;
  intent: RouteDeckNavigationIntent;
}

export interface RouteDeckClientOptions {
  baseUrl: string;
  fetch?: RouteDeckFetch;
  credentials?: RequestCredentials;
  http?: RouteDeckHttpTransport;
}

export function createRouteDeckClient(
  options: RouteDeckClientOptions,
): RouteDeckClient {
  const http =
    options.http ??
    createRouteDeckHttpTransport({
      baseUrl: options.baseUrl,
      ...(options.fetch === undefined ? {} : { fetch: options.fetch }),
      ...(options.credentials === undefined
        ? {}
        : { credentials: options.credentials }),
    });
  const privateForms = createPrivateFormClient(http);
  const decodeOperationResponse = (response: RouteDeckHttpResponse) =>
    decodeDispatchResult(response.value);
  const executeOperation = (
    path: string,
    request: RouteDeckDispatchRequest | RouteDeckReviewRequest,
  ): Promise<RouteDeckDispatchResult> =>
    executeRouteDeckMutation({
      http,
      path,
      requestId: request.request_id,
      method: "POST",
      body: request,
      decode: decodeOperationResponse,
      decodeClientError: decodeOperationResponse,
    });
  return {
    async getFrontendContract() {
      const response = requireSuccessfulResponse(await http.request("/contract"));
      return decodeFrontendContractEnvelope(response.value).frontend_contract;
    },
    async createSession(request) {
      return executeRouteDeckMutation({
        http,
        path: "/sessions",
        requestId: request.request_id,
        method: "POST",
        body: request,
        decode: (response) => decodeSessionEnvelope(response.value).projection,
      });
    },
    async getSession() {
      const response = requireSuccessfulResponse(await http.request("/session"));
      return decodeSessionEnvelope(response.value).projection;
    },
    async navigate(request) {
      return executeRouteDeckMutation({
        http,
        path: "/navigation",
        requestId: request.request_id,
        method: "POST",
        body: request,
        decode: (response) => decodeSessionEnvelope(response.value).projection,
      });
    },
    async dispatch(request) {
      return executeOperation("/dispatch", request);
    },
    async acceptReview(reviewId, request) {
      return executeOperation(
        `/reviews/${encodePathId(reviewId)}/accept`,
        request,
      );
    },
    async rejectReview(reviewId, request) {
      return executeOperation(
        `/reviews/${encodePathId(reviewId)}/reject`,
        request,
      );
    },
    async inspect() {
      const response = requireSuccessfulResponse(await http.request("/inspect"));
      return decodeInspection(response.value);
    },
    connectEvents(streamOptions) {
      return connectRouteDeckEvents({
        ...streamOptions,
        url: `${http.baseUrl}/events`,
        fetch: http.fetch,
        ...(options.credentials === undefined
          ? {}
          : { credentials: options.credentials }),
      });
    },
    privateForms,
  };
}

export function createRouteDeckRequestId(): string {
  const randomUuid = globalThis.crypto?.randomUUID?.bind(globalThis.crypto);
  if (!randomUuid) {
    throw new RouteDeckContractError(
      "$requestId",
      "crypto.randomUUID is required for globally unique request IDs",
    );
  }
  return randomUuid();
}

function encodePathId(value: string): string {
  if (!value || value.includes("/") || value.includes("\\")) {
    throw new RouteDeckContractError(
      "$pathId",
      "must be non-empty and contain no separator",
    );
  }
  return encodeURIComponent(value);
}
