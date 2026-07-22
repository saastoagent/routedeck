import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
} from "react";
import type {
  RouteDeckClientErrorState,
  RouteDeckClientState,
  RouteDeckStore,
} from "@routedeck/core";

import type {
  RouteDeckBootstrapRecoveryAction,
  RouteDeckBootstrapRecoveryActionKind,
  RouteDeckBootstrapRecoveryReason,
  RouteDeckBootstrapRecoveryState,
} from "./types";

export type {
  RouteDeckBootstrapActionRequiredState,
  RouteDeckBootstrapDisposedState,
  RouteDeckBootstrapLoadingState,
  RouteDeckBootstrapReadyState,
  RouteDeckBootstrapRecoveryAction,
  RouteDeckBootstrapRecoveryActionKind,
  RouteDeckBootstrapRecoveryReason,
  RouteDeckBootstrapRecoveryState,
} from "./types";

const RECOVERY_INCOMPLETE: RouteDeckClientErrorState = Object.freeze({
  code: "bootstrap_recovery_incomplete",
  message: "RouteDeck bootstrap recovery completed without a live session.",
});

const RECOVERY_FAILED: RouteDeckClientErrorState = Object.freeze({
  code: "bootstrap_recovery_failed",
  message: "RouteDeck bootstrap recovery failed.",
});

export function useRouteDeckBootstrapRecovery(
  store: RouteDeckStore,
): RouteDeckBootstrapRecoveryState {
  const state = useSyncExternalStore(
    store.subscribe,
    store.getState,
    store.getState,
  );
  const [activeAction, setActiveAction] =
    useState<RouteDeckBootstrapRecoveryActionKind | null>(null);
  const [actionFailure, setActionFailure] =
    useState<RouteDeckBootstrapActionFailure | null>(null);

  useEffect(() => {
    if (store.getState().syncStatus !== "idle") return;
    void store.bootstrap().catch(() => undefined);
  }, [store]);

  const runRecovery = useCallback(
    async (
      kind: RouteDeckBootstrapRecoveryActionKind,
      action: () => Promise<void>,
    ): Promise<void> => {
      setActiveAction(kind);
      setActionFailure(null);
      try {
        await action();
        const completed = store.getState();
        if (!isReady(completed)) {
          setActionFailure({
            state: completed,
            error: completed.error ?? RECOVERY_INCOMPLETE,
          });
        }
      } catch {
        const failed = store.getState();
        setActionFailure({
          state: failed,
          error: failed.error ?? RECOVERY_FAILED,
        });
      } finally {
        setActiveAction(null);
      }
    },
    [store],
  );

  const actions = useMemo(
    () => createRecoveryActions(store, runRecovery),
    [runRecovery, store],
  );
  const selection = selectRecovery(state);
  if (selection.phase === "disposed") {
    return {
      phase: "disposed",
      syncStatus: "disposed",
      busy: false,
      error: state.error,
      actions: [],
    };
  }
  if (selection.phase === "ready") {
    return {
      phase: "ready",
      syncStatus: "live",
      busy: false,
    };
  }
  if (selection.phase === "loading") {
    return {
      phase: "loading",
      syncStatus: state.syncStatus,
      busy: true,
    };
  }
  return {
    phase: "recovery",
    syncStatus: state.syncStatus,
    reason: selection.reason,
    busy: activeAction !== null || isInProgress(state),
    activeAction,
    error: actionFailure?.state === state ? actionFailure.error : state.error,
    actions: selection.actionKinds.map((kind) => actions[kind]),
  };
}

interface RouteDeckBootstrapActionFailure {
  readonly state: RouteDeckClientState;
  readonly error: RouteDeckClientErrorState;
}

type RunRecovery = (
  kind: RouteDeckBootstrapRecoveryActionKind,
  action: () => Promise<void>,
) => Promise<void>;

function createRecoveryActions(
  store: RouteDeckStore,
  runRecovery: RunRecovery,
): Readonly<
  Record<RouteDeckBootstrapRecoveryActionKind, RouteDeckBootstrapRecoveryAction>
> {
  return Object.freeze({
    retry_session_create: action("retry_session_create", () =>
      runRecovery("retry_session_create", store.retrySessionCreate),
    ),
    start_new_session: action("start_new_session", () =>
      runRecovery("start_new_session", store.startNewSession),
    ),
    retry_navigation: action("retry_navigation", () =>
      runRecovery("retry_navigation", store.retryNavigation),
    ),
    abandon_navigation: action("abandon_navigation", () =>
      runRecovery("abandon_navigation", store.abandonNavigation),
    ),
    resync: action("resync", () => runRecovery("resync", store.resync)),
  });
}

function action(
  kind: RouteDeckBootstrapRecoveryActionKind,
  run: () => Promise<void>,
): RouteDeckBootstrapRecoveryAction {
  return Object.freeze({ kind, run });
}

type RecoverySelection =
  | Readonly<{ phase: "loading" }>
  | Readonly<{ phase: "ready" }>
  | Readonly<{ phase: "disposed" }>
  | Readonly<{
      phase: "recovery";
      reason: RouteDeckBootstrapRecoveryReason;
      actionKinds: readonly RouteDeckBootstrapRecoveryActionKind[];
    }>;

function selectRecovery(state: RouteDeckClientState): RecoverySelection {
  if (state.syncStatus === "disposed") return { phase: "disposed" };
  if (state.pendingBootstrap !== null && state.pendingNavigation !== null) {
    return { phase: "recovery", reason: "invalid_state", actionKinds: [] };
  }
  if (state.syncStatus === "bootstrapping") return { phase: "loading" };
  if (state.pendingNavigation !== null) {
    return {
      phase: "recovery",
      reason: "navigation",
      actionKinds: ["retry_navigation", "abandon_navigation"],
    };
  }
  switch (state.pendingBootstrap?.kind) {
    case "session_create":
      return {
        phase: "recovery",
        reason: "session_create",
        actionKinds: ["retry_session_create", "start_new_session"],
      };
    case "resume_expired":
      return {
        phase: "recovery",
        reason: "resume_expired",
        actionKinds: ["start_new_session"],
      };
    case "resume_missing":
      return {
        phase: "recovery",
        reason: "resume_missing",
        actionKinds: ["start_new_session"],
      };
    case "resume_contract_mismatch":
      return {
        phase: "recovery",
        reason: "resume_contract_mismatch",
        actionKinds: ["start_new_session"],
      };
    default:
      break;
  }
  if (state.syncStatus === "live") return { phase: "ready" };
  if (state.syncStatus === "error") {
    return {
      phase: "recovery",
      reason: "resync",
      actionKinds: ["resync"],
    };
  }
  return { phase: "loading" };
}

function isReady(state: RouteDeckClientState): boolean {
  return (
    state.syncStatus === "live" &&
    state.pendingBootstrap === null &&
    state.pendingNavigation === null
  );
}

function isInProgress(state: RouteDeckClientState): boolean {
  return (
    state.syncStatus === "bootstrapping" ||
    state.syncStatus === "connecting" ||
    state.syncStatus === "navigating" ||
    state.syncStatus === "resyncing"
  );
}
