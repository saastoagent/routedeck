import {
  decodePrivateFormSaved,
  decodePrivateFormSnapshot,
  type JsonObject,
  type RouteDeckPrivateFormSaved,
  type RouteDeckPrivateFormSnapshot,
} from "../contracts/decode";
import type { RouteDeckHttpTransport } from "../client/http";
import {
  executeRouteDeckMutation,
  requireNoStore,
  requireSuccessfulResponse,
} from "../client/http";
import { RouteDeckContractError } from "../client/errors";

export interface RouteDeckPrivateFormClient {
  load(
    formId: string,
    options?: RouteDeckPrivateFormLoadOptions,
  ): Promise<RouteDeckPrivateFormSnapshot>;
  save(
    formId: string,
    request: RouteDeckPrivateFormSaveRequest,
  ): Promise<RouteDeckPrivateFormSaved>;
}

export interface RouteDeckPrivateFormSaveRequest {
  request_id: string;
  expected_session_version: number;
  value: JsonObject;
  complete?: boolean;
}

export interface RouteDeckPrivateFormLoadOptions {
  signal?: AbortSignal;
}

export function createPrivateFormClient(
  http: RouteDeckHttpTransport,
): RouteDeckPrivateFormClient {
  return {
    async load(formId, options = {}) {
      const response = requireSuccessfulResponse(
        await http.request(`/private-forms/${encodePathId(formId)}`, {
          cache: "no-store",
          ...(options.signal === undefined ? {} : { signal: options.signal }),
        }),
      );
      requireNoStore(response.headers, "$privateForm.headers");
      return decodePrivateFormSnapshot(response.value);
    },
    async save(formId, request) {
      const body = {
        request_id: request.request_id,
        expected_session_version: request.expected_session_version,
        value: request.value,
        ...(request.complete === undefined ? {} : { complete: request.complete }),
      };
      return executeRouteDeckMutation({
        http,
        path: `/private-forms/${encodePathId(formId)}`,
        requestId: request.request_id,
        method: "PUT",
        cache: "no-store",
        body,
        decode(response) {
          requireNoStore(response.headers, "$privateForm.headers");
          return decodePrivateFormSaved(response.value);
        },
      });
    },
  };
}

function encodePathId(value: string): string {
  if (!value || value.includes("/") || value.includes("\\")) {
    throw new RouteDeckContractError(
      "$privateForm.formId",
      "must be non-empty and contain no separator",
    );
  }
  return encodeURIComponent(value);
}
