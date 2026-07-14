import type {
  RouteDeckDispatchResult,
  RouteDeckProjection,
} from "../contracts/decode";
import {
  createRouteDeckRequestId,
  type RouteDeckClient,
  type RouteDeckSessionCreateRequest,
} from "../client/client";
import {
  RouteDeckHttpError,
  RouteDeckOutcomeUnknownError,
  RouteDeckStateError,
} from "../client/errors";
import { retainRouteDeckRequest } from "../client/retained";
import { RouteDeckEventStreamCoordinator } from "./events";
import {
  isExpiredBootstrapError,
  isMissingBootstrapError,
  isUpgradeBootstrapError,
  safeError,
} from "./errors";
import { RouteDeckObservableState } from "./observable";
import { RouteDeckNavigationCoordinator } from "./navigation";
import { RouteDeckRoutingCoordinator } from "./routing";
import type {
  InitialBootstrapContext,
  RetainedSessionCreateAttempt,
  RouteDeckStore,
  RouteDeckStoreConfig,
} from "./types";

export type {
  RouteDeckBootstrapMode,
  RouteDeckStore,
  RouteDeckStoreConfig,
} from "./types";

export function createRouteDeckStore(config: RouteDeckStoreConfig): RouteDeckStore {
  const observable = new RouteDeckObservableState();
  let state = observable.snapshot;
  const stopMirroringState = observable.subscribe(() => {
    state = observable.snapshot;
  });
  let resyncPromise: Promise<void> | null = null;
  let disposed = false;
  let resyncScheduled = false;
  let localReconciliationDepth = 0;
  let historyUnsubscribe: (() => void) | null = null;
  let bootstrapInFlight = false;
  let retainedSessionCreate: RetainedSessionCreateAttempt | null = null;
  const routing = new RouteDeckRoutingCoordinator(
    config,
    () => state.projection !== null,
  );
  const eventStream = new RouteDeckEventStreamCoordinator(
    config.client,
    observable,
    {
      isDisposed: () => disposed,
      state: () => state,
      receive: (event) => store.receiveEvent(event),
      scheduleResync,
    },
  );
  const navigation = new RouteDeckNavigationCoordinator(
    config,
    observable,
    routing,
    eventStream,
    {
      state: () => state,
      requireActive,
      reconcile: reconcileLocalRequest,
      applySnapshot: (projection) => applySnapshot(projection, "live"),
      resync: () => resyncFromServer("replace"),
    },
  );

  function requireActive(): void {
    if (disposed) {
      throw new RouteDeckStateError(
        "store_disposed",
        "The RouteDeck store has been disposed.",
      );
    }
  }

  function needsResync(): boolean {
    return state.syncStatus === "resync_required";
  }

  function requireBootstrapRecoveryAvailable(): void {
    if (bootstrapInFlight || navigation.inFlight || resyncPromise !== null) {
      throw new RouteDeckStateError(
        "bootstrap_in_progress",
        "RouteDeck bootstrap recovery is already in progress.",
      );
    }
  }

  function requireNewSessionRecovery(): void {
    const pending = state.pendingBootstrap;
    if (
      pending?.kind !== "session_create" &&
      pending?.kind !== "resume_expired" &&
      pending?.kind !== "resume_missing" &&
      pending?.kind !== "resume_contract_mismatch"
    ) {
      throw new RouteDeckStateError(
        "new_session_recovery_unavailable",
        "A new session is only available for uncertain, expired, or missing bootstrap recovery.",
      );
    }
  }

  function applySnapshot(
    projection: RouteDeckProjection,
    status: "live",
  ): void {
    const next = observable.applySnapshot(projection, status);
    if (next.syncStatus === "resync_required") {
      throw new RouteDeckStateError(
        next.error?.code ?? "snapshot_version_regressed",
        next.error?.message ?? "The RouteDeck snapshot version regressed.",
      );
    }
  }

  function scheduleResync(): void {
    if (resyncScheduled || disposed) return;
    resyncScheduled = true;
    queueMicrotask(() => {
      resyncScheduled = false;
      void store.resync().catch(() => undefined);
    });
  }

  async function reconcileLocalRequest<T>(request: () => Promise<T>): Promise<T> {
    localReconciliationDepth += 1;
    try {
      return await request();
    } finally {
      localReconciliationDepth -= 1;
      if (
        localReconciliationDepth === 0 &&
        needsResync()
      ) {
        scheduleResync();
      }
    }
  }

  async function bootstrapProjection(
    complete: RetainedSessionCreateAttempt["complete"],
  ): Promise<RouteDeckProjection | null> {
    const mode = config.bootstrapMode ?? "resume";
    if (mode === "create") {
      await executeSessionCreateAttempt(createSessionAttempt(complete));
      return null;
    }
    try {
      return await config.client.getSession();
    } catch (error) {
      if (
        mode !== "resume_or_create_shareable" ||
        !(error instanceof RouteDeckHttpError) ||
        error.status !== 404 ||
        error.failure?.code !== "session_not_found"
      ) {
        throw error;
      }
      if (!config.routes || !config.history) {
        throw new RouteDeckStateError(
          "shareable_bootstrap_requires_routing",
          "Shareable session creation requires the compiled route codec and history adapter.",
        );
      }
      if (config.routes.policyForPath(config.history.current()) !== "shareable") {
        throw error;
      }
      await executeSessionCreateAttempt(createSessionAttempt(complete));
      return null;
    }
  }

  function createSessionAttempt(
    complete: RetainedSessionCreateAttempt["complete"],
  ): RetainedSessionCreateAttempt {
    const retained = retainRouteDeckRequest<RouteDeckSessionCreateRequest>({
      request_id: (config.createRequestId ?? createRouteDeckRequestId)(),
    });
    return Object.freeze({
      request: retained.request,
      public: Object.freeze({
        kind: "session_create" as const,
      }),
      complete,
    });
  }

  async function executeSessionCreateAttempt(
    attempt: RetainedSessionCreateAttempt,
  ): Promise<void> {
    bootstrapInFlight = true;
    observable.startBootstrap(attempt.public);
    try {
      let projection: RouteDeckProjection;
      try {
        projection = await config.client.createSession(attempt.request);
      } catch (error) {
        if (error instanceof RouteDeckOutcomeUnknownError) {
          if (error.requestId !== attempt.request.request_id) {
            retainedSessionCreate = null;
            const mismatch = new RouteDeckStateError(
              "session_create_request_identity_mismatch",
              "The outcome-unknown failure does not match the retained session-create request.",
            );
            observable.setBootstrapFailure(safeError(mismatch), null);
            throw mismatch;
          }
          retainedSessionCreate = attempt;
          observable.setBootstrapFailure(safeError(error), attempt.public);
        } else {
          if (retainedSessionCreate === attempt) retainedSessionCreate = null;
          observable.setBootstrapFailure(safeError(error), null);
        }
        throw error;
      }

      if (retainedSessionCreate === attempt) retainedSessionCreate = null;
      observable.setPendingBootstrap(null);
      await attempt.complete(projection);
    } finally {
      bootstrapInFlight = false;
    }
  }

  async function applyOperationResult(
    result: RouteDeckDispatchResult,
    source: "dispatch" | "review",
  ): Promise<void> {
    if (
      (state.sessionVersion !== null &&
        result.session_version < state.sessionVersion) ||
      (state.projectionVersion !== null &&
        result.projection_version < state.projectionVersion)
    ) {
      observable.requireResync(
        `${source}_version_regressed`,
        "The RouteDeck operation result version regressed.",
      );
      await resyncFromServer("push");
    } else if (
      state.projection !== null &&
      result.projection_version > state.projection.projection_version
    ) {
      observable.requireResync(
        `${source}_snapshot_required`,
        "The RouteDeck operation changed the public projection.",
      );
      await resyncFromServer("push");
    } else {
      observable.advanceVersions(
        result.session_version,
        result.projection_version,
      );
    }
  }

  async function resyncFromServer(
    historyMode: "replace" | "push",
  ): Promise<void> {
    requireActive();
    if (resyncPromise) return resyncPromise;
    resyncPromise = (async () => {
      observable.startResync();
      eventStream.invalidate();
      try {
        const previousEntryId = state.projection?.navigation.current_entry_id;
        const projection = await config.client.getSession();
        applySnapshot(projection, "live");
        const effectiveMode =
          historyMode === "push" &&
          previousEntryId !== undefined &&
          previousEntryId !== projection.navigation.current_entry_id
            ? "push"
            : "replace";
        routing.syncHistory(projection, effectiveMode);
        await eventStream.connect(projection.event_cursor);
        ensureHistorySubscription();
      } catch (error) {
        observable.setError(safeError(error));
        throw error;
      } finally {
        resyncPromise = null;
      }
    })();
    return resyncPromise;
  }

  function ensureHistorySubscription(): void {
    if (config.history && historyUnsubscribe === null) {
      historyUnsubscribe = config.history.subscribe((path, entryId) =>
        navigation.enqueueHistoryRestore(path, entryId),
      );
    }
  }

  async function completeInitialBootstrap(
    initial: RouteDeckProjection,
    context: InitialBootstrapContext,
  ): Promise<void> {
    const finishBootstrap = async (projection: RouteDeckProjection) => {
      const mirrorsOpenedEntry =
        config.routes !== undefined &&
        context.incomingPath !== null &&
        context.incomingEntryId === null &&
        context.incomingPath !== routing.projectionPath(initial) &&
        projection.navigation.current_entry_id !==
          initial.navigation.current_entry_id;
      if (mirrorsOpenedEntry) routing.syncHistory(initial, "replace");
      if (projection !== initial) applySnapshot(projection, "live");
      routing.syncHistory(projection, mirrorsOpenedEntry ? "push" : "replace");
      await eventStream.connect(projection.event_cursor);
      ensureHistorySubscription();
    };
    applySnapshot(initial, "live");
    const intent = navigation.initialIntent(
      initial,
      context.incomingPath,
      context.incomingEntryId,
    );
    if (intent === null) {
      await finishBootstrap(initial);
      return;
    }
    await navigation.executeAttempt(
      navigation.createAttempt(initial, intent, finishBootstrap),
      false,
    );
  }

  const store: RouteDeckStore = {
    getState() {
      return state;
    },
    subscribe(listener) {
      requireActive();
      return observable.subscribe(listener);
    },
    async bootstrap() {
      requireActive();
      if (state.pendingBootstrap !== null || navigation.hasRetainedAttempt) {
        throw new RouteDeckStateError(
          "bootstrap_recovery_required",
          "Resolve the retained RouteDeck bootstrap request explicitly before bootstrapping again.",
        );
      }
      requireBootstrapRecoveryAvailable();
      bootstrapInFlight = true;
      observable.startBootstrap();
      try {
        const context: InitialBootstrapContext = Object.freeze({
          incomingPath: config.history?.current() ?? null,
          incomingEntryId: config.history?.currentEntryId() ?? null,
        });
        const initial = await bootstrapProjection((projection) =>
          completeInitialBootstrap(projection, context),
        );
        if (initial !== null) {
          await completeInitialBootstrap(initial, context);
        }
      } catch (error) {
        if (isExpiredBootstrapError(error)) {
          observable.setBootstrapFailure(safeError(error), {
              kind: "resume_expired",
              status: 410,
          });
        } else if (isMissingBootstrapError(error)) {
          observable.setBootstrapFailure(safeError(error), {
              kind: "resume_missing",
              status: 404,
          });
        } else if (isUpgradeBootstrapError(error)) {
          observable.setBootstrapFailure(safeError(error), {
              kind: "resume_contract_mismatch",
              status: 409,
          });
        } else {
          observable.setError(safeError(error));
        }
        throw error;
      } finally {
        bootstrapInFlight = false;
      }
    },
    async dispatch(request) {
      requireActive();
      if (state.projection === null || state.syncStatus !== "live") {
        throw new RouteDeckStateError(
          "store_not_ready",
          "RouteDeck dispatch requires a live bootstrapped store.",
        );
      }
      return reconcileLocalRequest(async () => {
        const result = await config.client.dispatch(request);
        await applyOperationResult(result, "dispatch");
        return result;
      });
    },
    async acceptReview(reviewId, request) {
      requireActive();
      if (state.projection === null || state.syncStatus !== "live") {
        throw new RouteDeckStateError(
          "store_not_ready",
          "RouteDeck review requires a live bootstrapped store.",
        );
      }
      return reconcileLocalRequest(async () => {
        const result = await config.client.acceptReview(reviewId, request);
        await applyOperationResult(result, "review");
        return result;
      });
    },
    async rejectReview(reviewId, request) {
      requireActive();
      if (state.projection === null || state.syncStatus !== "live") {
        throw new RouteDeckStateError(
          "store_not_ready",
          "RouteDeck review requires a live bootstrapped store.",
        );
      }
      return reconcileLocalRequest(async () => {
        const result = await config.client.rejectReview(reviewId, request);
        await applyOperationResult(result, "review");
        return result;
      });
    },
    async inspect() {
      requireActive();
      return config.client.inspect();
    },
    receiveEvent(event) {
      if (disposed) return;
      const next = observable.receiveEvent(event);
      if (
        next.syncStatus === "resync_required" &&
        localReconciliationDepth === 0
      ) {
        scheduleResync();
      }
    },
    async resync() {
      return resyncFromServer("replace");
    },
    async synchronizeTo(target) {
      requireActive();
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
      if (navigation.hasRetainedAttempt) {
        throw new RouteDeckStateError(
          "navigation_retry_required",
          "Resolve the retained navigation before synchronizing another interaction.",
        );
      }
      if (
        state.syncStatus === "live" &&
        state.sessionVersion !== null &&
        state.sessionVersion >= target.sessionVersion &&
        state.projectionVersion !== null &&
        state.projectionVersion >= target.projectionVersion
      ) {
        return;
      }
      await resyncFromServer("push");
      if (
        state.syncStatus !== "live" ||
        state.sessionVersion === null ||
        state.sessionVersion < target.sessionVersion ||
        state.projectionVersion === null ||
        state.projectionVersion < target.projectionVersion
      ) {
        const error = new RouteDeckStateError(
          "authoritative_version_unavailable",
          "The authoritative RouteDeck snapshot did not reach the interaction version.",
        );
        observable.setError(safeError(error));
        throw error;
      }
    },
    async openPath(path, options = {}) {
      await navigation.openPath(path, options.replace ?? false);
    },
    back() {
      navigation.back();
    },
    forward() {
      navigation.forward();
    },
    async cancel() {
      await navigation.cancel();
    },
    async retrySessionCreate() {
      requireActive();
      requireBootstrapRecoveryAvailable();
      if (retainedSessionCreate === null) {
        throw new RouteDeckStateError(
          "session_create_retry_missing",
          "There is no outcome-unknown session-create request to retry.",
        );
      }
      await executeSessionCreateAttempt(retainedSessionCreate);
    },
    async startNewSession() {
      requireActive();
      requireBootstrapRecoveryAvailable();
      requireNewSessionRecovery();
      eventStream.invalidate();
      historyUnsubscribe?.();
      historyUnsubscribe = null;
      retainedSessionCreate = null;
      navigation.reset();
      observable.resetForBootstrap();
      const freshContext: InitialBootstrapContext = Object.freeze({
        incomingPath: null,
        incomingEntryId: null,
      });
      await executeSessionCreateAttempt(
        createSessionAttempt((projection) =>
          completeInitialBootstrap(projection, freshContext),
        ),
      );
    },
    async retryNavigation() {
      await navigation.retry();
    },
    async abandonNavigation() {
      await navigation.abandon();
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      eventStream.dispose();
      historyUnsubscribe?.();
      historyUnsubscribe = null;
      retainedSessionCreate = null;
      navigation.reset();
      stopMirroringState();
      observable.dispose();
      state = observable.snapshot;
    },
  };
  return store;
}
