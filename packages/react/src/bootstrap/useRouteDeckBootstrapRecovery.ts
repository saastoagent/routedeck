import {
  useCallback,
  useEffect,
  useState,
  useSyncExternalStore,
} from "react";
import type {
  RouteDeckClientErrorState,
  RouteDeckClientState,
  RouteDeckStore,
} from "@routedeck/core";
import {
  runRouteDeckBootstrapRecoveryAction,
  selectRouteDeckBootstrapRecovery,
} from "@routedeck/core";

import type {
  RouteDeckBootstrapRecoveryAction,
  RouteDeckBootstrapRecoveryActionKind,
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
    async (kind: RouteDeckBootstrapRecoveryActionKind): Promise<void> => {
      setActiveAction(kind);
      setActionFailure(null);
      try {
        await runRouteDeckBootstrapRecoveryAction(store, kind);
        const completed = store.getState();
        if (selectRouteDeckBootstrapRecovery(completed).phase !== "ready") {
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

  const selection = selectRouteDeckBootstrapRecovery(state);
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
    busy: activeAction !== null,
    activeAction,
    error: actionFailure?.state === state ? actionFailure.error : state.error,
    actions:
      activeAction === null
        ? selection.actionKinds.map((kind) =>
            action(kind, () => runRecovery(kind)),
          )
        : [],
  };
}

interface RouteDeckBootstrapActionFailure {
  readonly state: RouteDeckClientState;
  readonly error: RouteDeckClientErrorState;
}

function action(
  kind: RouteDeckBootstrapRecoveryActionKind,
  run: () => Promise<void>,
): RouteDeckBootstrapRecoveryAction {
  return Object.freeze({ kind, run });
}
