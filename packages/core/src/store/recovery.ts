import { RouteDeckStateError } from "../client/errors";
import type { RouteDeckClientState } from "./state";
import type { RouteDeckStore } from "./types";

export type RouteDeckBootstrapRecoveryReason =
  | "session_create"
  | "resume_expired"
  | "resume_missing"
  | "resume_contract_mismatch"
  | "navigation"
  | "resync"
  | "invalid_state";

export type RouteDeckBootstrapRecoveryActionKind =
  | "retry_session_create"
  | "start_new_session"
  | "retry_navigation"
  | "abandon_navigation"
  | "resync";

export type RouteDeckBootstrapRecoverySelection =
  | Readonly<{ phase: "loading" }>
  | Readonly<{ phase: "ready" }>
  | Readonly<{ phase: "disposed" }>
  | Readonly<{
      phase: "recovery";
      reason: RouteDeckBootstrapRecoveryReason;
      actionKinds: readonly RouteDeckBootstrapRecoveryActionKind[];
    }>;

const LOADING = Object.freeze({ phase: "loading" as const });
const READY = Object.freeze({ phase: "ready" as const });
const DISPOSED = Object.freeze({ phase: "disposed" as const });
const INVALID_STATE = recovery("invalid_state", []);
const SESSION_CREATE = recovery("session_create", [
  "retry_session_create",
  "start_new_session",
]);
const RESUME_EXPIRED = recovery("resume_expired", ["start_new_session"]);
const RESUME_MISSING = recovery("resume_missing", ["start_new_session"]);
const RESUME_CONTRACT_MISMATCH = recovery("resume_contract_mismatch", [
  "start_new_session",
]);
const NAVIGATION = recovery("navigation", [
  "retry_navigation",
  "abandon_navigation",
]);
const RESYNC = recovery("resync", ["resync"]);

/**
 * Describes the current bootstrap/recovery phase without exposing retained
 * request identity or asking UI adapters to reconstruct store legality.
 */
export function selectRouteDeckBootstrapRecovery(
  state: RouteDeckClientState,
): RouteDeckBootstrapRecoverySelection {
  if (state.syncStatus === "disposed") return DISPOSED;
  if (state.pendingBootstrap !== null && state.pendingNavigation !== null) {
    return INVALID_STATE;
  }
  if (isRecoveryInProgress(state)) return LOADING;
  if (state.pendingNavigation !== null) return NAVIGATION;
  switch (state.pendingBootstrap?.kind) {
    case "session_create":
      return SESSION_CREATE;
    case "resume_expired":
      return RESUME_EXPIRED;
    case "resume_missing":
      return RESUME_MISSING;
    case "resume_contract_mismatch":
      return RESUME_CONTRACT_MISMATCH;
    default:
      break;
  }
  if (state.syncStatus === "live") return READY;
  if (state.syncStatus === "error") return RESYNC;
  return LOADING;
}

/**
 * Executes a recovery action only when it is legal for the store's current
 * canonical state. The check is repeated at invocation time so stale React
 * renders cannot bypass core recovery semantics.
 */
export async function runRouteDeckBootstrapRecoveryAction(
  store: RouteDeckStore,
  kind: RouteDeckBootstrapRecoveryActionKind,
): Promise<void> {
  const selection = selectRouteDeckBootstrapRecovery(store.getState());
  if (
    selection.phase !== "recovery" ||
    !selection.actionKinds.includes(kind)
  ) {
    throw new RouteDeckStateError(
      "bootstrap_recovery_action_unavailable",
      `RouteDeck bootstrap recovery action ${kind} is not available in the current state.`,
    );
  }
  switch (kind) {
    case "retry_session_create":
      return store.retrySessionCreate();
    case "start_new_session":
      return store.startNewSession();
    case "retry_navigation":
      return store.retryNavigation();
    case "abandon_navigation":
      return store.abandonNavigation();
    case "resync":
      return store.resync();
  }
}

function recovery(
  reason: RouteDeckBootstrapRecoveryReason,
  actionKinds: readonly RouteDeckBootstrapRecoveryActionKind[],
): RouteDeckBootstrapRecoverySelection {
  return Object.freeze({
    phase: "recovery" as const,
    reason,
    actionKinds: Object.freeze([...actionKinds]),
  });
}

function isRecoveryInProgress(state: RouteDeckClientState): boolean {
  return (
    state.syncStatus === "bootstrapping" ||
    state.syncStatus === "connecting" ||
    state.syncStatus === "navigating" ||
    state.syncStatus === "resyncing"
  );
}
