import type {
  RouteDeckEvent,
  RouteDeckProjection,
} from "../contracts/decode";
import {
  createInitialRouteDeckState,
  type RouteDeckClientErrorState,
  type RouteDeckClientState,
  type RouteDeckPendingBootstrap,
  type RouteDeckPendingNavigation,
  type RouteDeckSyncStatus,
} from "./state";


export class RouteDeckObservableState {
  readonly #listeners = new Set<() => void>();
  #snapshot: RouteDeckClientState = freezeState(createInitialRouteDeckState());

  get snapshot(): RouteDeckClientState {
    return this.#snapshot;
  }

  subscribe(listener: () => void): () => void {
    this.#listeners.add(listener);
    return () => this.#listeners.delete(listener);
  }

  applySnapshot(
    projection: RouteDeckProjection,
    syncStatus: RouteDeckSyncStatus = "live",
  ): RouteDeckClientState {
    const current = this.#snapshot;
    if (
      current.projection !== null &&
      (projection.event_cursor < current.eventCursor ||
        (current.sessionVersion !== null &&
          projection.session_version < current.sessionVersion) ||
        (current.projectionVersion !== null &&
          projection.projection_version < current.projectionVersion))
    ) {
      return this.requireResync(
        "snapshot_version_regressed",
        "The RouteDeck snapshot regressed a monotonic version.",
      );
    }
    return this.#commit({
      ...current,
      projection,
      sessionVersion: projection.session_version,
      projectionVersion: projection.projection_version,
      eventCursor: projection.event_cursor,
      syncStatus,
      error: null,
    });
  }

  receiveEvent(event: RouteDeckEvent): RouteDeckClientState {
    const current = this.#snapshot;
    if (event.cursor <= current.eventCursor) return current;
    if (event.cursor !== current.eventCursor + 1 || current.projection === null) {
      return this.requireResync(
        "event_gap",
        "The RouteDeck event stream has a cursor gap.",
      );
    }
    if (
      current.sessionVersion !== null &&
      event.session_version < current.sessionVersion
    ) {
      return this.requireResync(
        "session_version_regressed",
        "The RouteDeck event session version regressed.",
      );
    }
    if (
      event.projection_version !== null &&
      current.projectionVersion !== null &&
      event.projection_version < current.projectionVersion
    ) {
      return this.requireResync(
        "projection_version_regressed",
        "The RouteDeck event projection version regressed.",
      );
    }
    const projectionAdvanced =
      event.projection_version !== null &&
      current.projectionVersion !== null &&
      event.projection_version > current.projectionVersion;
    return this.#commit({
      ...current,
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
    });
  }

  requireResync(code: string, message: string): RouteDeckClientState {
    return this.#commit({
      ...this.#snapshot,
      syncStatus: "resync_required",
      error: { code, message },
    });
  }

  setSyncStatus(syncStatus: RouteDeckSyncStatus): RouteDeckClientState {
    return this.#commit({ ...this.#snapshot, syncStatus, error: null });
  }

  startBootstrap(
    pendingBootstrap: RouteDeckPendingBootstrap | null = null,
  ): RouteDeckClientState {
    return this.#commit({
      ...this.#snapshot,
      syncStatus: "bootstrapping",
      error: null,
      pendingBootstrap,
    });
  }

  startNavigation(
    pendingNavigation: RouteDeckPendingNavigation | null = null,
  ): RouteDeckClientState {
    return this.#commit({
      ...this.#snapshot,
      syncStatus: "navigating",
      error: null,
      pendingNavigation,
    });
  }

  startResync(
    pendingNavigation: RouteDeckPendingNavigation | null =
      this.#snapshot.pendingNavigation,
  ): RouteDeckClientState {
    return this.#commit({
      ...this.#snapshot,
      syncStatus: "resyncing",
      error: null,
      pendingNavigation,
    });
  }

  setError(error: RouteDeckClientErrorState): RouteDeckClientState {
    return this.#commit({ ...this.#snapshot, syncStatus: "error", error });
  }

  setBootstrapFailure(
    error: RouteDeckClientErrorState,
    pendingBootstrap: RouteDeckPendingBootstrap | null,
  ): RouteDeckClientState {
    return this.#commit({
      ...this.#snapshot,
      syncStatus: "error",
      error,
      pendingBootstrap,
    });
  }

  setPendingBootstrap(
    pendingBootstrap: RouteDeckPendingBootstrap | null,
  ): RouteDeckClientState {
    return this.#commit({ ...this.#snapshot, pendingBootstrap });
  }

  setNavigationFailure(
    error: RouteDeckClientErrorState,
    pendingNavigation: RouteDeckPendingNavigation | null,
  ): RouteDeckClientState {
    return this.#commit({
      ...this.#snapshot,
      syncStatus: "error",
      error,
      pendingNavigation,
    });
  }

  setPendingNavigation(
    pendingNavigation: RouteDeckPendingNavigation | null,
  ): RouteDeckClientState {
    return this.#commit({ ...this.#snapshot, pendingNavigation });
  }

  advanceVersions(
    sessionVersion: number,
    projectionVersion: number,
  ): RouteDeckClientState {
    return this.#commit({
      ...this.#snapshot,
      sessionVersion,
      projectionVersion,
    });
  }

  resetForBootstrap(): RouteDeckClientState {
    return this.#commit({
      ...createInitialRouteDeckState(),
      syncStatus: "bootstrapping",
    });
  }

  dispose(): void {
    this.#snapshot = freezeState({
      ...this.#snapshot,
      syncStatus: "disposed",
      pendingBootstrap: null,
      pendingNavigation: null,
    });
    this.#listeners.clear();
  }

  #commit(next: RouteDeckClientState): RouteDeckClientState {
    const frozen = freezeState(next);
    if (statesEqual(frozen, this.#snapshot)) return this.#snapshot;
    this.#snapshot = frozen;
    for (const listener of this.#listeners) listener();
    return frozen;
  }
}


function freezeState(state: RouteDeckClientState): RouteDeckClientState {
  return Object.freeze(state);
}


function statesEqual(
  left: RouteDeckClientState,
  right: RouteDeckClientState,
): boolean {
  return (
    left.projection === right.projection &&
    left.sessionVersion === right.sessionVersion &&
    left.projectionVersion === right.projectionVersion &&
    left.eventCursor === right.eventCursor &&
    left.syncStatus === right.syncStatus &&
    left.lastEvent === right.lastEvent &&
    left.error === right.error &&
    left.pendingBootstrap === right.pendingBootstrap &&
    left.pendingNavigation === right.pendingNavigation
  );
}
