import type {
  RouteDeckEvent,
  RouteDeckProjection,
} from "../contracts/decode";
import type { RouteDeckNavigationIntent } from "../client/client";

export type RouteDeckSyncStatus =
  | "idle"
  | "bootstrapping"
  | "connecting"
  | "navigating"
  | "live"
  | "resync_required"
  | "resyncing"
  | "error"
  | "disposed";

export interface RouteDeckClientErrorState {
  code: string;
  message: string;
}

export interface RouteDeckPendingNavigation {
  readonly requestId: string;
  readonly fingerprint: string;
  readonly intent: RouteDeckNavigationIntent;
}

export type RouteDeckPendingBootstrap =
  | Readonly<{
      /** Public status only; the replayable session-create identity remains private. */
      kind: "session_create";
    }>
  | Readonly<{
      kind: "resume_expired";
      status: 410;
    }>
  | Readonly<{
      kind: "resume_missing";
      status: 404;
    }>
  | Readonly<{
      kind: "resume_incompatible";
      status: 409;
    }>;

export interface RouteDeckClientState {
  projection: RouteDeckProjection | null;
  sessionVersion: number | null;
  projectionVersion: number | null;
  eventCursor: number;
  syncStatus: RouteDeckSyncStatus;
  lastEvent: RouteDeckEvent | null;
  error: RouteDeckClientErrorState | null;
  /** Explicit recovery metadata for bootstrap work that must not be guessed or replayed automatically. */
  pendingBootstrap: RouteDeckPendingBootstrap | null;
  pendingNavigation: RouteDeckPendingNavigation | null;
}

export function createInitialRouteDeckState(): RouteDeckClientState {
  return {
    projection: null,
    sessionVersion: null,
    projectionVersion: null,
    eventCursor: 0,
    syncStatus: "idle",
    lastEvent: null,
    error: null,
    pendingBootstrap: null,
    pendingNavigation: null,
  };
}
