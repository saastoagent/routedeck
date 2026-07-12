import {
  RouteDeckOutcomeUnknownError,
  RouteDeckStateError,
  retainRouteDeckRequest,
  type JsonObject,
  type RouteDeckDispatchRequest,
  type RouteDeckDispatchResult,
  type RouteDeckReviewRequest,
  type RouteDeckStore,
} from "@routedeck/core";

const EMPTY_ARGUMENTS: JsonObject = Object.freeze({});

export type RouteDeckPendingMutation = Readonly<{
  kind: "dispatch" | "review_accept" | "review_reject";
  requestId: string;
  fingerprint: string;
  operationId: string | null;
  reviewId: string | null;
}>;

export interface RouteDeckMutationControllerState {
  readonly pending: RouteDeckPendingMutation | null;
  readonly retrying: boolean;
  readonly inFlight: boolean;
}

export interface RouteDeckMutationController {
  getState(): RouteDeckMutationControllerState;
  subscribe(listener: () => void): () => void;
  dispatch(
    operationId: string,
    argumentsValue?: JsonObject,
  ): Promise<RouteDeckDispatchResult>;
  acceptReview(reviewId: string): Promise<RouteDeckDispatchResult>;
  rejectReview(reviewId: string): Promise<RouteDeckDispatchResult>;
  retry(): Promise<RouteDeckDispatchResult>;
  abandon(): Promise<void>;
}

type RetainedMutation =
  | Readonly<{
      kind: "dispatch";
      request: RouteDeckDispatchRequest;
      public: RouteDeckPendingMutation;
    }>
  | Readonly<{
      kind: "review_accept" | "review_reject";
      reviewId: string;
      request: RouteDeckReviewRequest;
      public: RouteDeckPendingMutation;
    }>;

export function createRouteDeckMutationController(options: {
  store: RouteDeckStore;
  createRequestId(): string;
}): RouteDeckMutationController {
  let state: RouteDeckMutationControllerState = Object.freeze({
    pending: null,
    retrying: false,
    inFlight: false,
  });
  let retained: RetainedMutation | null = null;
  let inFlight = false;
  const listeners = new Set<() => void>();

  const update = (next: RouteDeckMutationControllerState) => {
    state = Object.freeze(next);
    for (const listener of listeners) listener();
  };
  const requireAvailable = () => {
    if (inFlight) {
      throw new RouteDeckStateError(
        "mutation_in_progress",
        "A RouteDeck mutation is already in progress.",
      );
    }
    if (retained !== null) {
      throw new RouteDeckStateError(
        "mutation_retry_required",
        "A RouteDeck mutation has an unknown outcome; retry or abandon that exact request first.",
      );
    }
  };
  const retainUnknown = (
    mutation: RetainedMutation,
    error: RouteDeckOutcomeUnknownError,
  ) => {
    if (error.requestId !== mutation.request.request_id) {
      throw new RouteDeckStateError(
        "mutation_request_identity_mismatch",
        "The outcome-unknown failure does not match the retained RouteDeck request.",
      );
    }
    retained = mutation;
    update({ pending: mutation.public, retrying: false, inFlight: true });
  };
  const run = async (
    mutation: RetainedMutation,
    retrying: boolean,
  ): Promise<RouteDeckDispatchResult> => {
    inFlight = true;
    update({
      pending: retrying ? mutation.public : state.pending,
      retrying,
      inFlight: true,
    });
    try {
      const result =
        mutation.kind === "dispatch"
          ? await options.store.dispatch(mutation.request)
          : mutation.kind === "review_accept"
            ? await options.store.acceptReview(mutation.reviewId, mutation.request)
            : await options.store.rejectReview(mutation.reviewId, mutation.request);
      if (retained === mutation) retained = null;
      update({ pending: null, retrying: false, inFlight: true });
      return result;
    } catch (error) {
      if (error instanceof RouteDeckOutcomeUnknownError) {
        retainUnknown(mutation, error);
      } else if (retrying) {
        update({ pending: mutation.public, retrying: false, inFlight: true });
      }
      throw error;
    } finally {
      inFlight = false;
      update({ ...state, inFlight: false });
    }
  };
  const review = async (
    kind: "review_accept" | "review_reject",
    reviewId: string,
  ) => {
    requireAvailable();
    const { sessionVersion } = options.store.getState();
    if (sessionVersion === null) {
      throw new RouteDeckStateError(
        "store_not_ready",
        "RouteDeck review requires a bootstrapped session version.",
      );
    }
    const retainedRequest = retainRouteDeckRequest<RouteDeckReviewRequest>({
      request_id: options.createRequestId(),
      expected_session_version: sessionVersion,
    });
    const fingerprint = retainRouteDeckRequest({
      kind,
      review_id: reviewId,
      expected_session_version: sessionVersion,
    }).fingerprint;
    return run(
      Object.freeze({
        kind,
        reviewId,
        request: retainedRequest.request,
        public: Object.freeze({
          kind,
          requestId: retainedRequest.request.request_id,
          fingerprint,
          operationId: null,
          reviewId,
        }),
      }),
      false,
    );
  };

  return Object.freeze({
    getState: () => state,
    subscribe(listener: () => void) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    async dispatch(
      operationId: string,
      argumentsValue: JsonObject = EMPTY_ARGUMENTS,
    ) {
      requireAvailable();
      const { sessionVersion } = options.store.getState();
      if (sessionVersion === null) {
        throw new RouteDeckStateError(
          "store_not_ready",
          "RouteDeck dispatch requires a bootstrapped session version.",
        );
      }
      const retainedRequest = retainRouteDeckRequest<RouteDeckDispatchRequest>({
        operation_id: operationId,
        request_id: options.createRequestId(),
        expected_session_version: sessionVersion,
        arguments: argumentsValue,
      });
      const fingerprint = retainRouteDeckRequest({
        arguments: argumentsValue,
        expected_session_version: sessionVersion,
        operation_id: operationId,
      }).fingerprint;
      return run(
        Object.freeze({
          kind: "dispatch",
          request: retainedRequest.request,
          public: Object.freeze({
            kind: "dispatch",
            requestId: retainedRequest.request.request_id,
            fingerprint,
            operationId,
            reviewId: null,
          }),
        }),
        false,
      );
    },
    acceptReview: async (reviewId: string) => review("review_accept", reviewId),
    rejectReview: async (reviewId: string) => review("review_reject", reviewId),
    async retry() {
      if (inFlight) {
        throw new RouteDeckStateError(
          "mutation_in_progress",
          "The retained RouteDeck mutation is already being retried.",
        );
      }
      if (retained === null) {
        throw new RouteDeckStateError(
          "mutation_retry_missing",
          "There is no outcome-unknown RouteDeck mutation to retry.",
        );
      }
      return run(retained, true);
    },
    async abandon() {
      if (inFlight) {
        throw new RouteDeckStateError(
          "mutation_in_progress",
          "A RouteDeck mutation cannot be abandoned while it is in progress.",
        );
      }
      if (retained === null) {
        throw new RouteDeckStateError(
          "mutation_retry_missing",
          "There is no outcome-unknown RouteDeck mutation to abandon.",
        );
      }
      const pending = retained;
      inFlight = true;
      update({ pending: pending.public, retrying: true, inFlight: true });
      try {
        await options.store.resync();
        retained = null;
        update({ pending: null, retrying: false, inFlight: true });
      } catch (error) {
        update({ pending: pending.public, retrying: false, inFlight: true });
        throw error;
      } finally {
        inFlight = false;
        update({ ...state, inFlight: false });
      }
    },
  });
}
