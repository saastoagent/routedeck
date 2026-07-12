import {
  RouteDeckHttpError,
  RouteDeckOutcomeUnknownError,
  type RouteDeckDispatchRequest,
  type RouteDeckDispatchResult,
  type RouteDeckReviewRequest,
  type RouteDeckStore,
} from "@routedeck/core";
import { describe, expect, it, vi } from "vitest";

import { createRouteDeckMutationController } from "../operations/controller";

describe("RouteDeck retained dispatch controller", () => {
  it("publishes in-flight state until a normal dispatch fully settles", async () => {
    const result = {} as RouteDeckDispatchResult;
    let resolveDispatch!: (value: RouteDeckDispatchResult) => void;
    const controller = createRouteDeckMutationController({
      store: dispatchStore(
        () =>
          new Promise<RouteDeckDispatchResult>((resolve) => {
            resolveDispatch = resolve;
          }),
      ),
      createRequestId: () => "dispatch-in-flight",
    });
    const observed: boolean[] = [];
    const unsubscribe = controller.subscribe(() => {
      observed.push(controller.getState().inFlight);
    });

    const dispatch = controller.dispatch("catalog.list");

    expect(controller.getState()).toMatchObject({
      pending: null,
      retrying: false,
      inFlight: true,
    });
    await expect(controller.dispatch("catalog.search", {})).rejects.toMatchObject({
      code: "mutation_in_progress",
    });

    resolveDispatch(result);
    await expect(dispatch).resolves.toBe(result);
    expect(controller.getState()).toMatchObject({
      pending: null,
      retrying: false,
      inFlight: false,
    });
    expect(observed).toContain(true);
    expect(observed.at(-1)).toBe(false);
    unsubscribe();
  });

  it("retains an outcome-unknown request and retries its exact identity", async () => {
    const sent: RouteDeckDispatchRequest[] = [];
    const result = {} as RouteDeckDispatchResult;
    let attempt = 0;
    const store = dispatchStore(async (request) => {
      sent.push(request);
      attempt += 1;
      if (attempt === 1) {
        throw new RouteDeckOutcomeUnknownError(
          request.request_id,
          "The dispatch response was lost.",
        );
      }
      return result;
    });
    const createRequestId = vi.fn(() => "dispatch-request-stable");
    const controller = createRouteDeckMutationController({
      store,
      createRequestId,
    });

    await expect(
      controller.dispatch("cart.add", { quantity: 2, variant_ref: "variant-1" }),
    ).rejects.toBeInstanceOf(RouteDeckOutcomeUnknownError);

    expect(controller.getState().pending).toMatchObject({
      operationId: "cart.add",
      requestId: "dispatch-request-stable",
      fingerprint:
        '{"arguments":{"quantity":2,"variant_ref":"variant-1"},"expected_session_version":7,"operation_id":"cart.add"}',
    });
    await expect(controller.dispatch("cart.open")).rejects.toMatchObject({
        code: "mutation_retry_required",
    });

    await expect(controller.retry()).resolves.toBe(result);
    expect(sent).toHaveLength(2);
    expect(sent[1]).toBe(sent[0]);
    expect(createRequestId).toHaveBeenCalledOnce();
    expect(controller.getState().pending).toBeNull();
  });

  it("does not retain a confirmed HTTP rejection", async () => {
    const controller = createRouteDeckMutationController({
      store: dispatchStore(async () => {
        throw new RouteDeckHttpError(409, null, "Confirmed rejection");
      }),
      createRequestId: () => "confirmed-rejection",
    });

    await expect(controller.dispatch("cart.add", {})).rejects.toBeInstanceOf(
      RouteDeckHttpError,
    );
    expect(controller.getState().pending).toBeNull();
  });

  it("replays an outcome-unknown review decision with its original id", async () => {
    const requests: RouteDeckReviewRequest[] = [];
    const result = {} as RouteDeckDispatchResult;
    let attempt = 0;
    const store = {
      getState: () => ({ sessionVersion: 9 }),
      async acceptReview(_reviewId: string, request: RouteDeckReviewRequest) {
        requests.push(request);
        attempt += 1;
        if (attempt === 1) {
          throw new RouteDeckOutcomeUnknownError(
            request.request_id,
            "Review response was lost.",
          );
        }
        return result;
      },
      rejectReview: vi.fn(),
    } as unknown as RouteDeckStore;
    const createRequestId = vi.fn(() => "review-request-stable");
    const controller = createRouteDeckMutationController({
      store,
      createRequestId,
    });

    await expect(controller.acceptReview("review-opaque")).rejects.toBeInstanceOf(
      RouteDeckOutcomeUnknownError,
    );
    await expect(controller.rejectReview("different-review")).rejects.toMatchObject({
      code: "mutation_retry_required",
    });
    await expect(controller.retry()).resolves.toBe(result);

    expect(requests).toHaveLength(2);
    expect(requests[1]).toBe(requests[0]);
    expect(createRequestId).toHaveBeenCalledOnce();
  });
});

function dispatchStore(
  dispatch: (
    request: RouteDeckDispatchRequest,
  ) => Promise<RouteDeckDispatchResult>,
): RouteDeckStore {
  return {
    getState: () => ({ sessionVersion: 7 }),
    dispatch,
  } as unknown as RouteDeckStore;
}
