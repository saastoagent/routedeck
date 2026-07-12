import type {
  RouteDeckDispatchRequest,
  RouteDeckDispatchResult,
  RouteDeckEvent,
  RouteDeckInspection,
  RouteDeckProjection,
  RouteDeckReviewRequest,
} from "../contracts/decode";
import {
  createRouteDeckRequestId,
  type RouteDeckClient,
  type RouteDeckNavigationIntent,
  type RouteDeckNavigationRequest,
  type RouteDeckSessionCreateRequest,
} from "../client/client";
import {
  RouteDeckError,
  RouteDeckHttpError,
  RouteDeckOutcomeUnknownError,
  RouteDeckStateError,
  RouteDeckStreamError,
} from "../client/errors";
import { retainRouteDeckRequest } from "../client/retained";
import type { RouteDeckEventConnection } from "../client/sse";
import type { RouteDeckHistoryAdapter } from "../routing/history";
import type { RouteDeckRouteCodec } from "../routing/codec";
import {
  createRouteDeckRouteController,
  type RouteDeckRouteController,
} from "../routing/controller";
import {
  reduceEvent,
  reduceSnapshot,
  requireResync,
  setClientError,
  setSyncStatus,
} from "./reducer";
import {
  createInitialRouteDeckState,
  type RouteDeckClientErrorState,
  type RouteDeckClientState,
} from "./state";

export type RouteDeckBootstrapMode =
  | "resume"
  | "create"
  | "resume_or_create_shareable";

export interface RouteDeckStore {
  getState(): RouteDeckClientState;
  subscribe(listener: () => void): () => void;
  bootstrap(): Promise<void>;
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
  receiveEvent(event: RouteDeckEvent): void;
  resync(): Promise<void>;
  synchronizeTo(target: {
    sessionVersion: number;
    projectionVersion: number;
  }): Promise<void>;
  openPath(path: string, options?: { replace?: boolean }): Promise<void>;
  back(): void;
  forward(): void;
  cancel(): Promise<void>;
  /** Retry the one retained session-create request without changing its request ID. */
  retrySessionCreate(): Promise<void>;
  /** Explicitly abandon bootstrap recovery and create a fresh session request. */
  startNewSession(): Promise<void>;
  retryNavigation(): Promise<void>;
  abandonNavigation(): Promise<void>;
  dispose(): void;
}

export interface RouteDeckStoreConfig {
  client: RouteDeckClient;
  bootstrapMode?: RouteDeckBootstrapMode;
  history?: RouteDeckHistoryAdapter;
  routes?: RouteDeckRouteCodec;
  routeController?: RouteDeckRouteController;
  sessionAvailable?: () => boolean;
  resumeHandleForProjection?: (projection: RouteDeckProjection) => string | null;
  createRequestId?: () => string;
}

interface RetainedNavigationAttempt {
  readonly request: RouteDeckNavigationRequest;
  readonly public: NonNullable<RouteDeckClientState["pendingNavigation"]>;
  complete(projection: RouteDeckProjection): Promise<void>;
}

interface InitialBootstrapContext {
  readonly incomingPath: string | null;
  readonly incomingEntryId: number | null;
}

interface RetainedSessionCreateAttempt {
  readonly request: Readonly<RouteDeckSessionCreateRequest>;
  readonly public: Extract<
    NonNullable<RouteDeckClientState["pendingBootstrap"]>,
    { kind: "session_create" }
  >;
  complete(projection: RouteDeckProjection): Promise<void>;
}

export function createRouteDeckStore(config: RouteDeckStoreConfig): RouteDeckStore {
  let state = createInitialRouteDeckState();
  let eventConnection: RouteDeckEventConnection | null = null;
  let eventConnectionGeneration = 0;
  let resyncPromise: Promise<void> | null = null;
  let disposed = false;
  let resyncScheduled = false;
  let localReconciliationDepth = 0;
  let historyUnsubscribe: (() => void) | null = null;
  let navigationQueue = Promise.resolve();
  let bootstrapInFlight = false;
  let retainedSessionCreate: RetainedSessionCreateAttempt | null = null;
  let retainedNavigation: RetainedNavigationAttempt | null = null;
  let navigationInFlight = false;
  const listeners = new Set<() => void>();
  const routeController =
    config.routeController ??
    (config.history && config.routes
      ? createRouteDeckRouteController({
          history: config.history,
          codec: config.routes,
          context: () => ({
            sessionAvailable:
              config.sessionAvailable?.() ?? state.projection !== null,
          }),
        })
      : null);

  function update(next: RouteDeckClientState): void {
    if (next === state) return;
    state = next;
    for (const listener of listeners) listener();
  }

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

  function requireNavigationAvailable(): void {
    if (navigationInFlight) {
      throw new RouteDeckStateError(
        "navigation_in_progress",
        "A RouteDeck navigation is already in progress.",
      );
    }
    if (retainedNavigation !== null) {
      throw new RouteDeckStateError(
        "navigation_retry_required",
        "A RouteDeck navigation has an unknown outcome; retry or abandon that exact request first.",
      );
    }
  }

  function requireBootstrapRecoveryAvailable(): void {
    if (bootstrapInFlight || navigationInFlight || resyncPromise !== null) {
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
      pending?.kind !== "resume_incompatible"
    ) {
      throw new RouteDeckStateError(
        "new_session_recovery_unavailable",
        "A new session is only available for uncertain, expired, or missing bootstrap recovery.",
      );
    }
  }

  function invalidateEventConnection(): void {
    eventConnectionGeneration += 1;
    eventConnection?.close();
    eventConnection = null;
  }

  function projectionPath(projection: RouteDeckProjection): string {
    if (!config.routes) {
      throw new RouteDeckStateError(
        "routing_required",
        "RouteDeck URL synchronization requires compiled routes.",
      );
    }
    const params = Object.fromEntries(
      projection.current.route_params.map((parameter) => {
        if (typeof parameter.value !== "string") {
          throw new RouteDeckStateError(
            "route_parameter_invalid",
            `Route parameter ${parameter.name} must project as a string.`,
          );
        }
        return [parameter.name, parameter.value];
      }),
    );
    const resumeHandle = config.resumeHandleForProjection
      ? config.resumeHandleForProjection(projection)
      : projection.navigation.resume_handle;
    return config.routes.encode(projection.current.node_id, params, {
      ...(resumeHandle === null ? {} : { resumeHandle }),
    });
  }

  function syncHistory(
    projection: RouteDeckProjection,
    mode: "replace" | "push" | "verify" = "replace",
  ): void {
    if (!routeController || !config.history) return;
    if (mode === "verify") {
      if (
        config.history.current() !== projectionPath(projection) ||
        config.history.currentEntryId() !==
          projection.navigation.current_entry_id
      ) {
        throw new RouteDeckStateError(
          "browser_history_mismatch",
          "Browser history does not match the confirmed RouteDeck location.",
        );
      }
      return;
    }
    const resumeHandle = config.resumeHandleForProjection
      ? config.resumeHandleForProjection(projection)
      : projection.navigation.resume_handle;
    routeController.syncProjection(projection, {
      replace: mode === "replace",
      ...(resumeHandle === null ? {} : { resumeHandle }),
    });
  }

  function applySnapshot(
    projection: RouteDeckProjection,
    status: "live",
  ): void {
    const next = reduceSnapshot(state, projection, status);
    if (next.syncStatus === "resync_required") {
      update(next);
      throw new RouteDeckStateError(
        next.error?.code ?? "snapshot_version_regressed",
        next.error?.message ?? "The RouteDeck snapshot version regressed.",
      );
    }
    update(next);
  }

  function connect(after: number): Promise<void> {
    invalidateEventConnection();
    const generation = ++eventConnectionGeneration;
    let opened = false;
    let resolveOpen!: () => void;
    let rejectOpen!: (error: unknown) => void;
    const openPromise = new Promise<void>((resolve, reject) => {
      resolveOpen = resolve;
      rejectOpen = reject;
    });
    update(setSyncStatus(state, "connecting"));
    eventConnection = config.client.connectEvents({
      after,
      onOpen(open) {
        if (disposed || generation !== eventConnectionGeneration) return;
        if (open.reconnecting || state.syncStatus === "error") {
          const reconnectError = new RouteDeckStreamError(
            "stream_reconnected_snapshot_required",
            "The RouteDeck event stream reconnected and requires an authoritative snapshot.",
          );
          update(
            requireResync(
              state,
              reconnectError.code,
              reconnectError.message,
            ),
          );
          if (!opened) rejectOpen(reconnectError);
          scheduleResync();
          return;
        }
        if (state.syncStatus === "connecting") {
          update(setSyncStatus(state, "live"));
        }
        opened = true;
        resolveOpen();
      },
      onEvent(event) {
        if (disposed || generation !== eventConnectionGeneration) return;
        store.receiveEvent(event);
      },
      onReset() {
        if (disposed || generation !== eventConnectionGeneration) return;
        update(
          requireResync(
            state,
            "stream_reset_required",
            "The RouteDeck event cursor is outside retention.",
          ),
        );
        scheduleResync();
      },
      onError(error) {
        if (!disposed && generation === eventConnectionGeneration) {
          update(setClientError(state, safeError(error)));
          if (!opened) rejectOpen(error);
        }
      },
    });
    void eventConnection.done.catch((error: unknown) => {
      if (!disposed && generation === eventConnectionGeneration) {
        update(setClientError(state, safeError(error)));
        if (!opened) rejectOpen(error);
      }
    });
    return openPromise;
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
    update({
      ...setSyncStatus(state, "bootstrapping"),
      pendingBootstrap: attempt.public,
    });
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
            update({
              ...setClientError(state, safeError(mismatch)),
              pendingBootstrap: null,
            });
            throw mismatch;
          }
          retainedSessionCreate = attempt;
          update({
            ...setClientError(state, safeError(error)),
            pendingBootstrap: attempt.public,
          });
        } else {
          if (retainedSessionCreate === attempt) retainedSessionCreate = null;
          update({
            ...setClientError(state, safeError(error)),
            pendingBootstrap: null,
          });
        }
        throw error;
      }

      if (retainedSessionCreate === attempt) retainedSessionCreate = null;
      update({ ...state, pendingBootstrap: null });
      await attempt.complete(projection);
    } finally {
      bootstrapInFlight = false;
    }
  }

  function createNavigationAttempt(
    projection: RouteDeckProjection,
    intent: RouteDeckNavigationIntent,
    complete: RetainedNavigationAttempt["complete"],
  ): RetainedNavigationAttempt {
    requireNavigationAvailable();
    const expectedSessionVersion =
      state.sessionVersion ?? projection.session_version;
    const retained = retainRouteDeckRequest<RouteDeckNavigationRequest>({
      request_id: (config.createRequestId ?? createRouteDeckRequestId)(),
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

  async function executeNavigationAttempt(
    attempt: RetainedNavigationAttempt,
    retrying: boolean,
  ): Promise<void> {
    navigationInFlight = true;
    try {
      const projection = await config.client.navigate(attempt.request);
      await attempt.complete(projection);
      if (retainedNavigation === attempt) retainedNavigation = null;
      if (state.pendingNavigation !== null) {
        update({ ...state, pendingNavigation: null });
      }
    } catch (error) {
      if (error instanceof RouteDeckOutcomeUnknownError) {
        if (error.requestId !== attempt.request.request_id) {
          throw new RouteDeckStateError(
            "navigation_request_identity_mismatch",
            "The outcome-unknown failure does not match the retained navigation request.",
          );
        }
        retainedNavigation = attempt;
        update({
          ...setClientError(state, safeError(error)),
          pendingNavigation: attempt.public,
        });
      } else if (!retrying && state.pendingNavigation !== null) {
        retainedNavigation = null;
        update({ ...state, pendingNavigation: null });
      }
      throw error;
    } finally {
      navigationInFlight = false;
    }
  }

  function initialNavigationIntent(
    projection: RouteDeckProjection,
    incomingPath: string | null,
    incomingEntryId: number | null,
  ): RouteDeckNavigationIntent | null {
    if (!config.history || !config.routes || incomingPath === null) return null;
    const canonicalPath = projectionPath(projection);
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
    return {
      kind: "open_path",
      path: incomingPath,
    };
  }

  async function navigateAndSynchronize(
    intent: RouteDeckNavigationIntent,
    historyMode: "replace" | "push" | "verify",
  ): Promise<void> {
    requireNavigationAvailable();
    await reconcileLocalRequest(async () => {
      requireActive();
      const current = state.projection;
      if (current === null || state.syncStatus !== "live") {
        throw new RouteDeckStateError(
          "store_not_ready",
          "RouteDeck navigation requires a live bootstrapped store.",
        );
      }
      const attempt = createNavigationAttempt(
        current,
        intent,
        async (projection) => {
          applySnapshot(projection, "live");
          syncHistory(projection, historyMode);
        },
      );
      update(setSyncStatus(state, "navigating"));
      try {
        await executeNavigationAttempt(attempt, false);
      } catch (error) {
        if (
          !(error instanceof RouteDeckOutcomeUnknownError) &&
          !needsResync()
        ) {
          update(setClientError(state, safeError(error)));
        }
        throw error;
      }
    });
  }

  function enqueueHistoryRestore(
    path: string,
    historyEntryId: number | null,
  ): void {
    navigationQueue = navigationQueue
      .then(async () => {
        if (disposed) return;
        if (historyEntryId === null) {
          throw new RouteDeckStateError(
            "browser_history_identity_missing",
            "RouteDeck cannot restore browser history without its server entry identity.",
          );
        }
        await navigateAndSynchronize(
          {
            kind: "restore_history_entry",
            history_entry_id: historyEntryId,
            path,
          },
          "verify",
        );
      })
      .catch(async (error: unknown) => {
        if (disposed) return;
        update(setClientError(state, safeError(error)));
        if (error instanceof RouteDeckOutcomeUnknownError) return;
        try {
          await store.resync();
        } catch {
          // resync records the authoritative failure on the store.
        }
      });
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
      update(
        requireResync(
          state,
          `${source}_version_regressed`,
          "The RouteDeck operation result version regressed.",
        ),
      );
      await resyncFromServer("push");
    } else if (
      state.projection !== null &&
      result.projection_version > state.projection.projection_version
    ) {
      update(
        requireResync(
          state,
          `${source}_snapshot_required`,
          "The RouteDeck operation changed the public projection.",
        ),
      );
      await resyncFromServer("push");
    } else {
      update({
        ...state,
        sessionVersion: result.session_version,
        projectionVersion: result.projection_version,
      });
    }
  }

  async function resyncFromServer(
    historyMode: "replace" | "push",
  ): Promise<void> {
    requireActive();
    if (resyncPromise) return resyncPromise;
    resyncPromise = (async () => {
      update(setSyncStatus(state, "resyncing"));
      invalidateEventConnection();
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
        syncHistory(projection, effectiveMode);
        await connect(projection.event_cursor);
        ensureHistorySubscription();
      } catch (error) {
        update(setClientError(state, safeError(error)));
        throw error;
      } finally {
        resyncPromise = null;
      }
    })();
    return resyncPromise;
  }

  function ensureHistorySubscription(): void {
    if (config.history && historyUnsubscribe === null) {
      historyUnsubscribe = config.history.subscribe(enqueueHistoryRestore);
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
        context.incomingPath !== projectionPath(initial) &&
        projection.navigation.current_entry_id !==
          initial.navigation.current_entry_id;
      if (mirrorsOpenedEntry) syncHistory(initial, "replace");
      if (projection !== initial) applySnapshot(projection, "live");
      syncHistory(projection, mirrorsOpenedEntry ? "push" : "replace");
      await connect(projection.event_cursor);
      ensureHistorySubscription();
    };
    applySnapshot(initial, "live");
    const intent = initialNavigationIntent(
      initial,
      context.incomingPath,
      context.incomingEntryId,
    );
    if (intent === null) {
      await finishBootstrap(initial);
      return;
    }
    await executeNavigationAttempt(
      createNavigationAttempt(initial, intent, finishBootstrap),
      false,
    );
  }

  const store: RouteDeckStore = {
    getState() {
      return state;
    },
    subscribe(listener) {
      requireActive();
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    async bootstrap() {
      requireActive();
      if (state.pendingBootstrap !== null || retainedNavigation !== null) {
        throw new RouteDeckStateError(
          "bootstrap_recovery_required",
          "Resolve the retained RouteDeck bootstrap request explicitly before bootstrapping again.",
        );
      }
      requireBootstrapRecoveryAvailable();
      bootstrapInFlight = true;
      update(setSyncStatus(state, "bootstrapping"));
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
        const failed = setClientError(state, safeError(error));
        if (isExpiredBootstrapError(error)) {
          update({
            ...failed,
            pendingBootstrap: {
              kind: "resume_expired",
              status: 410,
            },
          });
        } else if (isMissingBootstrapError(error)) {
          update({
            ...failed,
            pendingBootstrap: {
              kind: "resume_missing",
              status: 404,
            },
          });
        } else if (isUpgradeBootstrapError(error)) {
          update({
            ...failed,
            pendingBootstrap: {
              kind: "resume_incompatible",
              status: 409,
            },
          });
        } else {
          update(failed);
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
      const next = reduceEvent(state, event);
      update(next);
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
      if (retainedNavigation !== null) {
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
        update(setClientError(state, safeError(error)));
        throw error;
      }
    },
    async openPath(path, options = {}) {
      requireNavigationAvailable();
      await navigateAndSynchronize(
        { kind: "open_path", path },
        options.replace ? "replace" : "push",
      );
    },
    back() {
      requireActive();
      requireNavigationAvailable();
      if (!config.history) {
        throw new RouteDeckStateError(
          "history_required",
          "RouteDeck back navigation requires a history adapter.",
        );
      }
      config.history.back();
    },
    forward() {
      requireActive();
      requireNavigationAvailable();
      if (!config.history) {
        throw new RouteDeckStateError(
          "history_required",
          "RouteDeck forward navigation requires a history adapter.",
        );
      }
      config.history.forward();
    },
    async cancel() {
      requireActive();
      requireNavigationAvailable();
      const projection = state.projection;
      if (
        config.history &&
        projection !== null &&
        state.syncStatus === "live" &&
        projection.navigation.can_cancel &&
        projection.navigation.can_back &&
        projection.navigation.cancel_target_node_id === null
      ) {
        config.history.back();
        return;
      }
      await navigateAndSynchronize({ kind: "cancel" }, "replace");
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
      invalidateEventConnection();
      historyUnsubscribe?.();
      historyUnsubscribe = null;
      retainedSessionCreate = null;
      retainedNavigation = null;
      navigationQueue = Promise.resolve();
      update({
        ...createInitialRouteDeckState(),
        syncStatus: "bootstrapping",
      });
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
      requireActive();
      if (navigationInFlight) {
        throw new RouteDeckStateError(
          "navigation_in_progress",
          "The retained RouteDeck navigation is already being retried.",
        );
      }
      if (retainedNavigation === null) {
        throw new RouteDeckStateError(
          "navigation_retry_missing",
          "There is no outcome-unknown RouteDeck navigation to retry.",
        );
      }
      const attempt = retainedNavigation;
      update({
        ...setSyncStatus(state, "navigating"),
        pendingNavigation: attempt.public,
      });
      try {
        await executeNavigationAttempt(attempt, true);
      } catch (error) {
        if (!(error instanceof RouteDeckOutcomeUnknownError)) {
          update({
            ...setClientError(state, safeError(error)),
            pendingNavigation: attempt.public,
          });
        }
        throw error;
      }
    },
    async abandonNavigation() {
      requireActive();
      if (navigationInFlight) {
        throw new RouteDeckStateError(
          "navigation_in_progress",
          "A RouteDeck navigation cannot be abandoned while it is in progress.",
        );
      }
      if (retainedNavigation === null) {
        throw new RouteDeckStateError(
          "navigation_retry_missing",
          "There is no outcome-unknown RouteDeck navigation to abandon.",
        );
      }
      const attempt = retainedNavigation;
      update({
        ...setSyncStatus(state, "resyncing"),
        pendingNavigation: attempt.public,
      });
      invalidateEventConnection();
      try {
        const projection = await config.client.getSession();
        await attempt.complete(projection);
        if (eventConnection === null) {
          await connect(projection.event_cursor);
        }
        if (retainedNavigation === attempt) retainedNavigation = null;
        update({ ...state, pendingNavigation: null });
      } catch (error) {
        update({
          ...setClientError(state, safeError(error)),
          pendingNavigation: attempt.public,
        });
        throw error;
      }
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      eventConnection?.close();
      eventConnectionGeneration += 1;
      eventConnection = null;
      historyUnsubscribe?.();
      historyUnsubscribe = null;
      retainedSessionCreate = null;
      retainedNavigation = null;
      navigationInFlight = false;
      listeners.clear();
      state = {
        ...state,
        syncStatus: "disposed",
        pendingBootstrap: null,
        pendingNavigation: null,
      };
    },
  };
  return store;
}

function safeError(error: unknown): RouteDeckClientErrorState {
  if (
    error instanceof RouteDeckError ||
    error instanceof RouteDeckStreamError
  ) {
    return { code: error.code, message: error.message };
  }
  return {
    code: "unexpected_client_failure",
    message: "The RouteDeck client encountered an unexpected failure.",
  };
}

function isExpiredBootstrapError(error: unknown): boolean {
  return (
    (error instanceof RouteDeckHttpError ||
      error instanceof RouteDeckStreamError) &&
    error.status === 410
  );
}

function isMissingBootstrapError(error: unknown): boolean {
  return (
    (error instanceof RouteDeckHttpError &&
      error.status === 404 &&
      error.failure?.code === "session_not_found") ||
    (error instanceof RouteDeckStreamError &&
      error.status === 404 &&
      error.code === "stream_session_not_found")
  );
}

function isUpgradeBootstrapError(error: unknown): boolean {
  return (
    error instanceof RouteDeckHttpError &&
    error.status === 409 &&
    error.failure?.code === "session_upgrade_required"
  );
}
