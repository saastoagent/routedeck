import type {
  RouteDeckDispatchRequest,
  RouteDeckDispatchResult,
  RouteDeckInspection,
  RouteDeckReviewRequest,
} from "../contracts/decode";
import { RouteDeckStateError } from "../client/errors";
import type { RouteDeckObservableState } from "./observable";
import type { RouteDeckClientState } from "./state";
import type { RouteDeckStoreConfig } from "./types";

export interface RouteDeckOperationHost {
  state(): RouteDeckClientState;
  requireActive(): void;
  reconcile<T>(request: () => Promise<T>): Promise<T>;
  resync(): Promise<void>;
}

export class RouteDeckOperationCoordinator {
  constructor(
    private readonly config: RouteDeckStoreConfig,
    private readonly observable: RouteDeckObservableState,
    private readonly host: RouteDeckOperationHost,
  ) {}

  async dispatch(
    request: RouteDeckDispatchRequest,
  ): Promise<RouteDeckDispatchResult> {
    this.requireReady("dispatch");
    return this.host.reconcile(async () => {
      const result = await this.config.client.dispatch(request);
      await this.applyResult(result, "dispatch");
      return result;
    });
  }

  async acceptReview(
    reviewId: string,
    request: RouteDeckReviewRequest,
  ): Promise<RouteDeckDispatchResult> {
    this.requireReady("review");
    return this.host.reconcile(async () => {
      const result = await this.config.client.acceptReview(reviewId, request);
      await this.applyResult(result, "review");
      return result;
    });
  }

  async rejectReview(
    reviewId: string,
    request: RouteDeckReviewRequest,
  ): Promise<RouteDeckDispatchResult> {
    this.requireReady("review");
    return this.host.reconcile(async () => {
      const result = await this.config.client.rejectReview(reviewId, request);
      await this.applyResult(result, "review");
      return result;
    });
  }

  async inspect(): Promise<RouteDeckInspection> {
    this.host.requireActive();
    return this.config.client.inspect();
  }

  private requireReady(operation: "dispatch" | "review"): void {
    this.host.requireActive();
    const state = this.host.state();
    if (state.projection === null || state.syncStatus !== "live") {
      throw new RouteDeckStateError(
        "store_not_ready",
        `RouteDeck ${operation} requires a live bootstrapped store.`,
      );
    }
  }

  private async applyResult(
    result: RouteDeckDispatchResult,
    source: "dispatch" | "review",
  ): Promise<void> {
    const state = this.host.state();
    if (
      (state.sessionVersion !== null &&
        result.session_version < state.sessionVersion) ||
      (state.projectionVersion !== null &&
        result.projection_version < state.projectionVersion)
    ) {
      this.observable.requireResync(
        `${source}_version_regressed`,
        "The RouteDeck operation result version regressed.",
      );
      await this.host.resync();
    } else if (
      state.projection !== null &&
      result.projection_version > state.projection.projection_version
    ) {
      this.observable.requireResync(
        `${source}_snapshot_required`,
        "The RouteDeck operation changed the public projection.",
      );
      await this.host.resync();
    } else {
      this.observable.advanceVersions(
        result.session_version,
        result.projection_version,
      );
    }
  }
}
