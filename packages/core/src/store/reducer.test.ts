import { describe, expect, it } from "vitest";

import type {
  RouteDeckEvent,
  RouteDeckProjection,
} from "../contracts/decode";
import {
  createInitialRouteDeckState,
  type RouteDeckClientState,
  type RouteDeckSyncStatus,
} from "./state";
import {
  reduceEvent,
  reduceSnapshot,
  requireResync,
  setClientError,
  setSyncStatus,
} from "./reducer";

describe("RouteDeck client reducer", () => {
  it("accepts an initial snapshot and an equal monotonic replacement", () => {
    const initial = createInitialRouteDeckState();
    const first = reduceSnapshot(initial, projection());

    expect(first).toMatchObject({
      sessionVersion: 1,
      projectionVersion: 1,
      eventCursor: 0,
      syncStatus: "live",
      error: null,
    });
    expect(first.projection).toEqual(projection());

    const replacement = projection({ session: 1, projection: 1, cursor: 0 });
    const replaced = reduceSnapshot(first, replacement, "resyncing");
    expect(replaced.projection).toBe(replacement);
    expect(replaced.syncStatus).toBe("resyncing");
  });

  it.each([
    {
      label: "event cursor",
      state: state({ cursor: 3, session: 3, projection: 3 }),
      snapshot: projection({ cursor: 2, session: 3, projection: 3 }),
    },
    {
      label: "session version",
      state: state({ cursor: 3, session: 3, projection: 3 }),
      snapshot: projection({ cursor: 3, session: 2, projection: 3 }),
    },
    {
      label: "projection version",
      state: state({
        cursor: 3,
        session: null,
        projection: 3,
      }),
      snapshot: projection({ cursor: 3, session: 3, projection: 2 }),
    },
  ])("requires resync when a snapshot regresses $label", ({ state, snapshot }) => {
    expect(reduceSnapshot(state, snapshot)).toMatchObject({
      projection: state.projection,
      syncStatus: "resync_required",
      error: { code: "snapshot_version_regressed" },
    });
  });

  it("ignores replayed events and detects cursor gaps or missing snapshots", () => {
    const current = state({ cursor: 2, session: 2, projection: 2 });
    expect(reduceEvent(current, event({ cursor: 2 }))).toBe(current);
    expect(reduceEvent(current, event({ cursor: 4 }))).toMatchObject({
      syncStatus: "resync_required",
      error: { code: "event_gap" },
    });

    const withoutSnapshot = {
      ...createInitialRouteDeckState(),
      eventCursor: 2,
    };
    expect(reduceEvent(withoutSnapshot, event({ cursor: 3 }))).toMatchObject({
      syncStatus: "resync_required",
      error: { code: "event_gap" },
    });
  });

  it("rejects regressed event versions", () => {
    const current = state({ cursor: 2, session: 4, projection: 4 });

    expect(
      reduceEvent(
        current,
        event({ cursor: 3, session: 3, projection: 4 }),
      ),
    ).toMatchObject({
      syncStatus: "resync_required",
      error: { code: "session_version_regressed" },
    });
    expect(
      reduceEvent(
        current,
        event({ cursor: 3, session: 4, projection: 3 }),
      ),
    ).toMatchObject({
      syncStatus: "resync_required",
      error: { code: "projection_version_regressed" },
    });
  });

  it("applies an in-order event without forcing a snapshot", () => {
    const current = state({
      cursor: 2,
      session: null,
      projection: null,
    });
    const next = event({ cursor: 3, session: 3, projection: null });
    const reduced = reduceEvent(current, next);

    expect(reduced).toMatchObject({
      sessionVersion: 3,
      projectionVersion: null,
      eventCursor: 3,
      lastEvent: next,
      syncStatus: "live",
      error: null,
    });
  });

  it("requires a snapshot when an event advances the projection version", () => {
    const current = state({ cursor: 2, session: 2, projection: 2 });
    const next = event({ cursor: 3, session: 3, projection: 3 });

    expect(reduceEvent(current, next)).toMatchObject({
      sessionVersion: 3,
      projectionVersion: 2,
      eventCursor: 3,
      lastEvent: next,
      syncStatus: "resync_required",
      error: { code: "projection_snapshot_required" },
    });
  });

  it("exposes explicit sync and error transitions", () => {
    const current = state({ cursor: 1, session: 1, projection: 1 });
    const resyncing = setSyncStatus(
      requireResync(current, "manual_resync", "Refresh required."),
      "resyncing",
    );
    expect(resyncing).toMatchObject({ syncStatus: "resyncing", error: null });

    expect(
      setClientError(resyncing, {
        code: "stream_failed",
        message: "The event stream stopped.",
      }),
    ).toMatchObject({
      syncStatus: "error",
      error: {
        code: "stream_failed",
        message: "The event stream stopped.",
      },
    });
  });
});

function state(options: {
  cursor: number;
  session: number | null;
  projection: number | null;
  syncStatus?: RouteDeckSyncStatus;
}): RouteDeckClientState {
  return {
    ...createInitialRouteDeckState(),
    projection: projection({
      cursor: options.cursor,
      session: options.session ?? 1,
      projection: options.projection ?? 1,
    }),
    eventCursor: options.cursor,
    sessionVersion: options.session,
    projectionVersion: options.projection,
    syncStatus: options.syncStatus ?? "live",
  };
}

function projection(
  options: { cursor?: number; session?: number; projection?: number } = {},
): RouteDeckProjection {
  const location = { node_id: "home", route_params: [] };
  return {
    current: location,
    diagnostics: {
      schema_version: 1,
      navgraph_version: "test-navgraph-v1",
      current_node_id: "home",
      declared_provider_ids: [],
    },
    entities: [],
    event_cursor: options.cursor ?? 0,
    failure: null,
    legal_operations: [],
    navigation: {
      current: location,
      current_entry_id: 1,
      route_template: "/",
      resume_handle: null,
      can_back: false,
      can_forward: false,
      can_cancel: false,
      back_node_id: null,
      forward_node_id: null,
      cancel_target_node_id: null,
    },
    projection_version: options.projection ?? 1,
    session_version: options.session ?? 1,
    status: { code: "ready", message: null },
    surfaces: {
      active: { surface_id: "test.active", component: "test.active", props: [] },
      detail: [],
      diagnostic: [],
      error: [],
      form: [],
      frame: [],
      peer: [],
      review: [],
      status: [],
    },
  };
}

function event(options: {
  cursor: number;
  session?: number;
  projection?: number | null;
}): RouteDeckEvent {
  return {
    event_id: `event-${options.cursor}`,
    cursor: options.cursor,
    event_type: "operation_changed",
    session_version: options.session ?? options.cursor,
    projection_version: options.projection ?? null,
    created_at: "2029-01-01T00:00:00.000Z",
    payload: {
      node_id: null,
      operation_id: null,
      request_id: null,
      status_code: "ready",
      entity_handles: [],
      details: [],
      failure: null,
    },
  };
}
