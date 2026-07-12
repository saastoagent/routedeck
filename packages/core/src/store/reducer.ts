import type {
  RouteDeckEvent,
  RouteDeckProjection,
} from "../contracts/decode";
import type {
  RouteDeckClientErrorState,
  RouteDeckClientState,
  RouteDeckSyncStatus,
} from "./state";

export function reduceSnapshot(
  state: RouteDeckClientState,
  projection: RouteDeckProjection,
  syncStatus: RouteDeckSyncStatus = "live",
): RouteDeckClientState {
  if (
    state.projection !== null &&
    (projection.event_cursor < state.eventCursor ||
      (state.sessionVersion !== null &&
        projection.session_version < state.sessionVersion) ||
      (state.projectionVersion !== null &&
        projection.projection_version < state.projectionVersion))
  ) {
    return requireResync(
      state,
      "snapshot_version_regressed",
      "The RouteDeck snapshot regressed a monotonic version.",
    );
  }
  return {
    ...state,
    projection,
    sessionVersion: projection.session_version,
    projectionVersion: projection.projection_version,
    eventCursor: projection.event_cursor,
    syncStatus,
    error: null,
  };
}

export function reduceEvent(
  state: RouteDeckClientState,
  event: RouteDeckEvent,
): RouteDeckClientState {
  if (event.cursor <= state.eventCursor) return state;
  if (event.cursor !== state.eventCursor + 1 || state.projection === null) {
    return requireResync(state, "event_gap", "The RouteDeck event stream has a cursor gap.");
  }
  if (
    state.sessionVersion !== null &&
    event.session_version < state.sessionVersion
  ) {
    return requireResync(
      state,
      "session_version_regressed",
      "The RouteDeck event session version regressed.",
    );
  }
  if (
    event.projection_version !== null &&
    state.projectionVersion !== null &&
    event.projection_version < state.projectionVersion
  ) {
    return requireResync(
      state,
      "projection_version_regressed",
      "The RouteDeck event projection version regressed.",
    );
  }
  const projectionAdvanced =
    event.projection_version !== null &&
    state.projectionVersion !== null &&
    event.projection_version > state.projectionVersion;
  return {
    ...state,
    sessionVersion: event.session_version,
    eventCursor: event.cursor,
    lastEvent: event,
    syncStatus: projectionAdvanced ? "resync_required" : "live",
    error: projectionAdvanced
      ? {
          code: "projection_snapshot_required",
          message: "A newer RouteDeck projection snapshot is required.",
        }
      : null,
  };
}

export function requireResync(
  state: RouteDeckClientState,
  code: string,
  message: string,
): RouteDeckClientState {
  return {
    ...state,
    syncStatus: "resync_required",
    error: { code, message },
  };
}

export function setSyncStatus(
  state: RouteDeckClientState,
  syncStatus: RouteDeckSyncStatus,
): RouteDeckClientState {
  return { ...state, syncStatus, error: null };
}

export function setClientError(
  state: RouteDeckClientState,
  error: RouteDeckClientErrorState,
): RouteDeckClientState {
  return { ...state, syncStatus: "error", error };
}
