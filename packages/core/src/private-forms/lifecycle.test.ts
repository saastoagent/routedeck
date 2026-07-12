import { describe, expect, it, vi } from "vitest";

import type {
  JsonObject,
  RouteDeckPrivateFormSnapshot,
} from "../contracts/decode";
import type { RouteDeckHttpTransport } from "../client/http";
import { RouteDeckOutcomeUnknownError } from "../client/errors";
import {
  createPrivateFormClient,
  type RouteDeckPrivateFormClient,
} from "./client";
import { createPrivateFormState } from "./state";

const FORM_ID = "form_opaque_abort_contract";
const SNAPSHOT: RouteDeckPrivateFormSnapshot = Object.freeze({
  form_id: FORM_ID,
  revision: 1,
  complete: true,
  session_version: 4,
  value: Object.freeze({}),
});
const SNAPSHOT_JSON: JsonObject = Object.freeze({
  form_id: FORM_ID,
  revision: 1,
  complete: true,
  session_version: 4,
  value: Object.freeze({}),
});

describe("private-form load cancellation", () => {
  it("forwards the caller AbortSignal to the HTTP transport", async () => {
    const request = vi.fn(async () => ({
      status: 200,
      ok: true,
      value: SNAPSHOT_JSON,
      headers: new Headers({ "cache-control": "no-store" }),
    }));
    const http: RouteDeckHttpTransport = {
      baseUrl: "/api/routedeck",
      fetch: vi.fn(),
      request,
    };
    const client = createPrivateFormClient(http);
    const controller = new AbortController();

    await expect(
      client.load(FORM_ID, { signal: controller.signal }),
    ).resolves.toEqual(SNAPSHOT);
    expect(request).toHaveBeenCalledWith(`/private-forms/${FORM_ID}`, {
      cache: "no-store",
      signal: controller.signal,
    });
  });

  it("does not cache a load that became obsolete before completion", async () => {
    let finishLoad!: (snapshot: RouteDeckPrivateFormSnapshot) => void;
    let receivedSignal: AbortSignal | undefined;
    const client: RouteDeckPrivateFormClient = {
      load: vi.fn((_, options) => {
        receivedSignal = options?.signal;
        return new Promise<RouteDeckPrivateFormSnapshot>((resolve) => {
          finishLoad = resolve;
        });
      }),
      save: vi.fn(async () => {
        throw new Error("save is outside this cancellation test");
      }),
    };
    const state = createPrivateFormState(client);
    const controller = new AbortController();

    const pending = state.load(FORM_ID, { signal: controller.signal });
    controller.abort();
    finishLoad(SNAPSHOT);

    await expect(pending).rejects.toMatchObject({ name: "AbortError" });
    expect(receivedSignal).toBe(controller.signal);
    expect(state.get(FORM_ID)).toBeNull();
  });
});

describe("private-form save outcome recovery", () => {
  it("retains one exact save request for explicit retry", async () => {
    const requests: Array<{
      request_id: string;
      expected_session_version: number;
      value: JsonObject;
      complete?: boolean;
    }> = [];
    let attempt = 0;
    const client: RouteDeckPrivateFormClient = {
      load: vi.fn(async () => SNAPSHOT),
      async save(_formId, request) {
        requests.push(request);
        attempt += 1;
        if (attempt === 1) {
          throw new RouteDeckOutcomeUnknownError(
            request.request_id,
            "Private-form response was lost.",
          );
        }
        return {
          form_id: FORM_ID,
          revision: 2,
          complete: true,
          session_version: 5,
          projection_version: 2,
        };
      },
    };
    const state = createPrivateFormState(client);

    await expect(
      state.save(FORM_ID, {
        request_id: "private-save-stable",
        expected_session_version: 4,
        value: { email: "buyer@example.test" },
        complete: true,
      }),
    ).rejects.toBeInstanceOf(RouteDeckOutcomeUnknownError);

    expect(state.getPendingSave()).toMatchObject({
      formId: FORM_ID,
      requestId: "private-save-stable",
    });
    await expect(
      state.save(FORM_ID, {
        request_id: "private-save-new",
        expected_session_version: 4,
        value: { email: "different@example.test" },
      }),
    ).rejects.toMatchObject({ code: "private_form_save_retry_required" });

    await expect(state.retrySave()).resolves.toMatchObject({ revision: 2 });
    expect(requests).toHaveLength(2);
    expect(requests[1]).toBe(requests[0]);
    expect(state.getPendingSave()).toBeNull();
  });
});
