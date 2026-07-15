import type {
  RouteDeckEvent,
  RouteDeckProjection,
} from "../contracts/decode";
import { RouteDeckStateError } from "../client/errors";
import type { RouteDeckEventStreamCoordinator } from "./events";
import { safeError } from "./errors";
import type { RouteDeckNavigationCoordinator } from "./navigation";
import type { RouteDeckObservableState } from "./observable";
import type { RouteDeckRoutingCoordinator } from "./routing";
import type { RouteDeckClientState } from "./state";
import type {
  InitialBootstrapContext,
  RouteDeckStoreConfig,
} from "./types";

export interface RouteDeckSynchronizationHost {
  state(): RouteDeckClientState;
  isDisposed(): boolean;
  requireActive(): void;
}

export class RouteDeckSynchronizationCoordinator {
  private resyncPromise: Promise<void> | null = null;
  private resyncScheduled = false;
  private localReconciliationDepth = 0;
  private historyUnsubscribe: (() => void) | null = null;

  constructor(
    private readonly config: RouteDeckStoreConfig,
    private readonly observable: RouteDeckObservableState,
    private readonly routing: RouteDeckRoutingCoordinator,
    private readonly eventStream: RouteDeckEventStreamCoordinator,
    private readonly navigation: RouteDeckNavigationCoordinator,
    private readonly host: RouteDeckSynchronizationHost,
  ) {}

  get resyncInFlight(): boolean {
    return this.resyncPromise !== null;
  }

  applySnapshot(projection: RouteDeckProjection): void {
    const next = this.observable.applySnapshot(projection, "live");
    if (next.syncStatus === "resync_required") {
      throw new RouteDeckStateError(
        next.error?.code ?? "snapshot_version_regressed",
        next.error?.message ?? "The RouteDeck snapshot version regressed.",
      );
    }
  }

  scheduleResync(): void {
    if (this.resyncScheduled || this.host.isDisposed()) return;
    this.resyncScheduled = true;
    queueMicrotask(() => {
      this.resyncScheduled = false;
      void this.resync("replace").catch(() => undefined);
    });
  }

  async reconcile<T>(request: () => Promise<T>): Promise<T> {
    this.localReconciliationDepth += 1;
    try {
      return await request();
    } finally {
      this.localReconciliationDepth -= 1;
      if (
        this.localReconciliationDepth === 0 &&
        this.host.state().syncStatus === "resync_required"
      ) {
        this.scheduleResync();
      }
    }
  }

  async resync(historyMode: "replace" | "push"): Promise<void> {
    this.host.requireActive();
    if (this.resyncPromise) return this.resyncPromise;
    const resync = (async () => {
      this.observable.startResync();
      this.eventStream.invalidate();
      try {
        const previousEntryId =
          this.host.state().projection?.navigation.current_entry_id;
        const projection = await this.config.client.getSession();
        this.applySnapshot(projection);
        const effectiveMode =
          historyMode === "push" &&
          previousEntryId !== undefined &&
          previousEntryId !== projection.navigation.current_entry_id
            ? "push"
            : "replace";
        this.routing.syncHistory(projection, effectiveMode);
        await this.eventStream.connect(projection.event_cursor);
        this.ensureHistorySubscription();
      } catch (error) {
        this.observable.setError(safeError(error));
        throw error;
      } finally {
        this.resyncPromise = null;
      }
    })();
    this.resyncPromise = resync;
    return resync;
  }

  async completeInitialBootstrap(
    initial: RouteDeckProjection,
    context: InitialBootstrapContext,
  ): Promise<void> {
    const finishBootstrap = async (projection: RouteDeckProjection) => {
      const mirrorsOpenedEntry =
        this.config.routes !== undefined &&
        context.incomingPath !== null &&
        context.incomingEntryId === null &&
        context.incomingPath !== this.routing.projectionPath(initial) &&
        projection.navigation.current_entry_id !==
          initial.navigation.current_entry_id;
      if (mirrorsOpenedEntry) this.routing.syncHistory(initial, "replace");
      if (projection !== initial) this.applySnapshot(projection);
      this.routing.syncHistory(
        projection,
        mirrorsOpenedEntry ? "push" : "replace",
      );
      await this.eventStream.connect(projection.event_cursor);
      this.ensureHistorySubscription();
    };
    this.applySnapshot(initial);
    const intent = this.navigation.initialIntent(
      initial,
      context.incomingPath,
      context.incomingEntryId,
    );
    if (intent === null) {
      await finishBootstrap(initial);
      return;
    }
    await this.navigation.executeAttempt(
      this.navigation.createAttempt(initial, intent, finishBootstrap),
      false,
    );
  }

  receiveEvent(event: RouteDeckEvent): void {
    if (this.host.isDisposed()) return;
    const next = this.observable.receiveEvent(event);
    if (
      next.syncStatus === "resync_required" &&
      this.localReconciliationDepth === 0
    ) {
      this.scheduleResync();
    }
  }

  async synchronizeTo(target: {
    sessionVersion: number;
    projectionVersion: number;
  }): Promise<void> {
    this.host.requireActive();
    if (
      !Number.isInteger(target.sessionVersion) ||
      target.sessionVersion < 0 ||
      !Number.isInteger(target.projectionVersion) ||
      target.projectionVersion < 0
    ) {
      throw new RouteDeckStateError(
        "synchronization_target_invalid",
        "RouteDeck synchronization targets must be non-negative integers.",
      );
    }
    if (this.navigation.hasRetainedAttempt) {
      throw new RouteDeckStateError(
        "navigation_retry_required",
        "Resolve the retained navigation before synchronizing another interaction.",
      );
    }
    const current = this.host.state();
    if (
      current.syncStatus === "live" &&
      current.sessionVersion !== null &&
      current.sessionVersion >= target.sessionVersion &&
      current.projectionVersion !== null &&
      current.projectionVersion >= target.projectionVersion
    ) {
      return;
    }
    await this.resync("push");
    const synchronized = this.host.state();
    if (
      synchronized.syncStatus !== "live" ||
      synchronized.sessionVersion === null ||
      synchronized.sessionVersion < target.sessionVersion ||
      synchronized.projectionVersion === null ||
      synchronized.projectionVersion < target.projectionVersion
    ) {
      const error = new RouteDeckStateError(
        "authoritative_version_unavailable",
        "The authoritative RouteDeck snapshot did not reach the interaction version.",
      );
      this.observable.setError(safeError(error));
      throw error;
    }
  }

  prepareNewSession(): void {
    this.eventStream.invalidate();
    this.clearHistorySubscription();
  }

  dispose(): void {
    this.clearHistorySubscription();
  }

  private ensureHistorySubscription(): void {
    if (this.config.history && this.historyUnsubscribe === null) {
      this.historyUnsubscribe = this.config.history.subscribe((path, entryId) =>
        this.navigation.enqueueHistoryRestore(path, entryId),
      );
    }
  }

  private clearHistorySubscription(): void {
    this.historyUnsubscribe?.();
    this.historyUnsubscribe = null;
  }
}
