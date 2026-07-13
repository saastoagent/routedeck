import type { RouteDeckProjection } from "../contracts/decode";
import {
  createRouteDeckRequestId,
  type RouteDeckNavigationIntent,
  type RouteDeckNavigationRequest,
} from "../client/client";
import {
  RouteDeckOutcomeUnknownError,
  RouteDeckStateError,
} from "../client/errors";
import { retainRouteDeckRequest } from "../client/retained";
import type { RouteDeckEventStreamCoordinator } from "./events";
import { safeError } from "./errors";
import type { RouteDeckObservableState } from "./observable";
import type { RouteDeckRoutingCoordinator } from "./routing";
import type { RouteDeckClientState } from "./state";
import type {
  RetainedNavigationAttempt,
  RouteDeckStoreConfig,
} from "./types";

export interface RouteDeckNavigationHost {
  state(): RouteDeckClientState;
  requireActive(): void;
  reconcile<T>(request: () => Promise<T>): Promise<T>;
  applySnapshot(projection: RouteDeckProjection): void;
  resync(): Promise<void>;
}

export class RouteDeckNavigationCoordinator {
  private retained: RetainedNavigationAttempt | null = null;
  private running = false;
  private queue = Promise.resolve();

  constructor(
    private readonly config: RouteDeckStoreConfig,
    private readonly observable: RouteDeckObservableState,
    private readonly routing: RouteDeckRoutingCoordinator,
    private readonly eventStream: RouteDeckEventStreamCoordinator,
    private readonly host: RouteDeckNavigationHost,
  ) {}

  get inFlight(): boolean {
    return this.running;
  }

  get hasRetainedAttempt(): boolean {
    return this.retained !== null;
  }

  requireAvailable(): void {
    if (this.running) {
      throw new RouteDeckStateError(
        "navigation_in_progress",
        "A RouteDeck navigation is already in progress.",
      );
    }
    if (this.retained !== null) {
      throw new RouteDeckStateError(
        "navigation_retry_required",
        "A RouteDeck navigation has an unknown outcome; retry or abandon that exact request first.",
      );
    }
  }

  createAttempt(
    projection: RouteDeckProjection,
    intent: RouteDeckNavigationIntent,
    complete: RetainedNavigationAttempt["complete"],
  ): RetainedNavigationAttempt {
    this.requireAvailable();
    const state = this.host.state();
    const expectedSessionVersion =
      state.sessionVersion ?? projection.session_version;
    const retained = retainRouteDeckRequest<RouteDeckNavigationRequest>({
      request_id: (this.config.createRequestId ?? createRouteDeckRequestId)(),
      expected_session_version: expectedSessionVersion,
      intent,
    });
    const fingerprint = retainRouteDeckRequest({
      expected_session_version: expectedSessionVersion,
      intent,
    }).fingerprint;
    return Object.freeze({
      request: retained.request,
      public: Object.freeze({
        requestId: retained.request.request_id,
        fingerprint,
        intent: retained.request.intent,
      }),
      complete,
    });
  }

  async executeAttempt(
    attempt: RetainedNavigationAttempt,
    retrying: boolean,
  ): Promise<void> {
    this.running = true;
    try {
      const projection = await this.config.client.navigate(attempt.request);
      await attempt.complete(projection);
      if (this.retained === attempt) this.retained = null;
      if (this.host.state().pendingNavigation !== null) {
        this.observable.setPendingNavigation(null);
      }
    } catch (error) {
      if (error instanceof RouteDeckOutcomeUnknownError) {
        if (error.requestId !== attempt.request.request_id) {
          throw new RouteDeckStateError(
            "navigation_request_identity_mismatch",
            "The outcome-unknown failure does not match the retained navigation request.",
          );
        }
        this.retained = attempt;
        this.observable.setNavigationFailure(safeError(error), attempt.public);
      } else if (!retrying && this.host.state().pendingNavigation !== null) {
        this.retained = null;
        this.observable.setPendingNavigation(null);
      }
      throw error;
    } finally {
      this.running = false;
    }
  }

  initialIntent(
    projection: RouteDeckProjection,
    incomingPath: string | null,
    incomingEntryId: number | null,
  ): RouteDeckNavigationIntent | null {
    if (!this.config.history || !this.config.routes || incomingPath === null) {
      return null;
    }
    const canonicalPath = this.routing.projectionPath(projection);
    if (
      incomingPath === canonicalPath &&
      (incomingEntryId === null ||
        incomingEntryId === projection.navigation.current_entry_id)
    ) {
      return null;
    }
    if (incomingEntryId !== null) {
      return {
        kind: "restore_history_entry",
        history_entry_id: incomingEntryId,
        path: incomingPath,
      };
    }
    return { kind: "open_path", path: incomingPath };
  }

  async navigateAndSynchronize(
    intent: RouteDeckNavigationIntent,
    historyMode: "replace" | "push" | "verify",
  ): Promise<void> {
    this.requireAvailable();
    await this.host.reconcile(async () => {
      this.host.requireActive();
      const state = this.host.state();
      const current = state.projection;
      if (current === null || state.syncStatus !== "live") {
        throw new RouteDeckStateError(
          "store_not_ready",
          "RouteDeck navigation requires a live bootstrapped store.",
        );
      }
      const attempt = this.createAttempt(current, intent, async (projection) => {
        this.host.applySnapshot(projection);
        this.routing.syncHistory(projection, historyMode);
      });
      this.observable.startNavigation();
      try {
        await this.executeAttempt(attempt, false);
      } catch (error) {
        if (
          !(error instanceof RouteDeckOutcomeUnknownError) &&
          this.host.state().syncStatus !== "resync_required"
        ) {
          this.observable.setError(safeError(error));
        }
        throw error;
      }
    });
  }

  enqueueHistoryRestore(path: string, historyEntryId: number | null): void {
    this.queue = this.queue
      .then(async () => {
        if (this.host.state().syncStatus === "disposed") return;
        if (historyEntryId === null) {
          throw new RouteDeckStateError(
            "browser_history_identity_missing",
            "RouteDeck cannot restore browser history without its server entry identity.",
          );
        }
        await this.navigateAndSynchronize(
          {
            kind: "restore_history_entry",
            history_entry_id: historyEntryId,
            path,
          },
          "verify",
        );
      })
      .catch(async (error: unknown) => {
        if (this.host.state().syncStatus === "disposed") return;
        this.observable.setError(safeError(error));
        if (error instanceof RouteDeckOutcomeUnknownError) return;
        try {
          await this.host.resync();
        } catch {
          // resync records the authoritative failure on the store.
        }
      });
  }

  async openPath(path: string, replace = false): Promise<void> {
    await this.navigateAndSynchronize(
      { kind: "open_path", path },
      replace ? "replace" : "push",
    );
  }

  back(): void {
    this.host.requireActive();
    this.requireAvailable();
    if (!this.config.history) {
      throw new RouteDeckStateError(
        "history_required",
        "RouteDeck back navigation requires a history adapter.",
      );
    }
    this.config.history.back();
  }

  forward(): void {
    this.host.requireActive();
    this.requireAvailable();
    if (!this.config.history) {
      throw new RouteDeckStateError(
        "history_required",
        "RouteDeck forward navigation requires a history adapter.",
      );
    }
    this.config.history.forward();
  }

  async cancel(): Promise<void> {
    this.host.requireActive();
    this.requireAvailable();
    const state = this.host.state();
    const projection = state.projection;
    if (
      this.config.history &&
      projection !== null &&
      state.syncStatus === "live" &&
      projection.navigation.can_cancel &&
      projection.navigation.can_back &&
      projection.navigation.cancel_target_node_id === null
    ) {
      this.config.history.back();
      return;
    }
    await this.navigateAndSynchronize({ kind: "cancel" }, "replace");
  }

  async retry(): Promise<void> {
    this.host.requireActive();
    if (this.running) {
      throw new RouteDeckStateError(
        "navigation_in_progress",
        "The retained RouteDeck navigation is already being retried.",
      );
    }
    if (this.retained === null) {
      throw new RouteDeckStateError(
        "navigation_retry_missing",
        "There is no outcome-unknown RouteDeck navigation to retry.",
      );
    }
    const attempt = this.retained;
    this.observable.startNavigation(attempt.public);
    try {
      await this.executeAttempt(attempt, true);
    } catch (error) {
      if (!(error instanceof RouteDeckOutcomeUnknownError)) {
        this.observable.setNavigationFailure(safeError(error), attempt.public);
      }
      throw error;
    }
  }

  async abandon(): Promise<void> {
    this.host.requireActive();
    if (this.running) {
      throw new RouteDeckStateError(
        "navigation_in_progress",
        "A RouteDeck navigation cannot be abandoned while it is in progress.",
      );
    }
    if (this.retained === null) {
      throw new RouteDeckStateError(
        "navigation_retry_missing",
        "There is no outcome-unknown RouteDeck navigation to abandon.",
      );
    }
    const attempt = this.retained;
    this.observable.startResync(attempt.public);
    this.eventStream.invalidate();
    try {
      const projection = await this.config.client.getSession();
      await attempt.complete(projection);
      if (!this.eventStream.connected) {
        await this.eventStream.connect(projection.event_cursor);
      }
      if (this.retained === attempt) this.retained = null;
      this.observable.setPendingNavigation(null);
    } catch (error) {
      this.observable.setNavigationFailure(safeError(error), attempt.public);
      throw error;
    }
  }

  reset(): void {
    this.retained = null;
    this.running = false;
    this.queue = Promise.resolve();
  }
}
