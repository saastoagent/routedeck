import { expect, test } from "vitest";

import type { RouteDeckEvent, RouteDeckProjection } from "../contracts/decode";
import { RouteDeckObservableState } from "./observable";
import type {
  RouteDeckPendingBootstrap,
  RouteDeckPendingNavigation,
} from "./state";


test("named state actions publish one immutable snapshot per change", () => {
  const observable = new RouteDeckObservableState();
  const snapshots: string[] = [];
  observable.subscribe(() => snapshots.push(observable.snapshot.syncStatus));

  observable.setSyncStatus("bootstrapping");
  observable.applySnapshot(projection());

  expect(snapshots).toEqual(["bootstrapping", "live"]);
  expect(observable.snapshot).toMatchObject({
    sessionVersion: 1,
    projectionVersion: 1,
    eventCursor: 0,
    syncStatus: "live",
  });
});

test("disposal preserves the last projection in an immutable terminal snapshot", () => {
  const observable = new RouteDeckObservableState();
  const current = projection();

  observable.applySnapshot(current);
  observable.dispose();

  expect(observable.snapshot).toMatchObject({
    projection: current,
    sessionVersion: 1,
    projectionVersion: 1,
    eventCursor: 0,
    syncStatus: "disposed",
  });
  expect(Object.isFrozen(observable.snapshot)).toBe(true);
});

test("subscription removal and equal actions do not publish redundant snapshots", () => {
  const observable = new RouteDeckObservableState();
  let notifications = 0;
  const unsubscribe = observable.subscribe(() => notifications += 1);

  const original = observable.snapshot;
  expect(observable.setSyncStatus("idle")).toBe(original);
  unsubscribe();
  observable.setSyncStatus("connecting");

  expect(notifications).toBe(0);
});

test.each([
  ["event cursor", { event_cursor: 1 }, { event_cursor: 0 }],
  ["session version", { session_version: 2 }, { session_version: 1 }],
  ["projection version", { projection_version: 2 }, { projection_version: 1 }],
])("a snapshot rejects a regressed %s", (_label, currentPatch, nextPatch) => {
  const observable = new RouteDeckObservableState();
  observable.applySnapshot({ ...projection(), ...currentPatch });

  const state = observable.applySnapshot({
    ...projection(),
    ...currentPatch,
    ...nextPatch,
  });

  expect(state).toMatchObject({
    syncStatus: "resync_required",
    error: { code: "snapshot_version_regressed" },
  });
});

test("events ignore replays and require a contiguous snapshot-backed cursor", () => {
  const observable = new RouteDeckObservableState();

  expect(observable.receiveEvent(event({ cursor: 0 }))).toBe(observable.snapshot);
  expect(observable.receiveEvent(event({ cursor: 2 }))).toMatchObject({
    syncStatus: "resync_required",
    error: { code: "event_gap" },
  });

  const fresh = new RouteDeckObservableState();
  fresh.applySnapshot(projection());
  expect(fresh.receiveEvent(event({ cursor: 2 }))).toMatchObject({
    syncStatus: "resync_required",
    error: { code: "event_gap" },
  });
});

test("events reject regressed session and projection versions", () => {
  const sessionRegression = new RouteDeckObservableState();
  sessionRegression.applySnapshot({ ...projection(), session_version: 2 });
  expect(
    sessionRegression.receiveEvent(event({ session_version: 1 })),
  ).toMatchObject({
    syncStatus: "resync_required",
    error: { code: "session_version_regressed" },
  });

  const projectionRegression = new RouteDeckObservableState();
  projectionRegression.applySnapshot({ ...projection(), projection_version: 2 });
  expect(
    projectionRegression.receiveEvent(event({ projection_version: 1 })),
  ).toMatchObject({
    syncStatus: "resync_required",
    error: { code: "projection_version_regressed" },
  });
});

test("events advance live state or require a newer projection snapshot", () => {
  const observable = new RouteDeckObservableState();
  observable.applySnapshot(projection());

  const live = observable.receiveEvent(event({ projection_version: null }));
  expect(live).toMatchObject({
    eventCursor: 1,
    sessionVersion: 1,
    syncStatus: "live",
    error: null,
  });

  const advanced = observable.receiveEvent(
    event({ cursor: 2, session_version: 2, projection_version: 2 }),
  );
  expect(advanced).toMatchObject({
    eventCursor: 2,
    sessionVersion: 2,
    syncStatus: "resync_required",
    error: { code: "projection_snapshot_required" },
  });
});

test("named lifecycle actions preserve exact recovery metadata", () => {
  const observable = new RouteDeckObservableState();
  const bootstrap = { kind: "session_create" } satisfies RouteDeckPendingBootstrap;
  const navigation = {
    requestId: "navigation-1",
    fingerprint: "fingerprint-1",
    intent: { kind: "back" },
  } satisfies RouteDeckPendingNavigation;
  const error = { code: "failed", message: "The operation failed." };

  expect(observable.startBootstrap().pendingBootstrap).toBeNull();
  expect(observable.startBootstrap(bootstrap)).toMatchObject({
    syncStatus: "bootstrapping",
    pendingBootstrap: bootstrap,
  });
  expect(observable.setPendingBootstrap(null).pendingBootstrap).toBeNull();
  expect(observable.setBootstrapFailure(error, bootstrap)).toMatchObject({
    syncStatus: "error",
    error,
    pendingBootstrap: bootstrap,
  });
  expect(observable.startNavigation()).toMatchObject({
    syncStatus: "navigating",
    pendingNavigation: null,
  });
  expect(observable.startNavigation(navigation).pendingNavigation).toBe(navigation);
  expect(observable.startResync().pendingNavigation).toBe(navigation);
  expect(observable.startResync(null)).toMatchObject({
    syncStatus: "resyncing",
    pendingNavigation: null,
  });
  expect(observable.setPendingNavigation(navigation).pendingNavigation).toBe(
    navigation,
  );
  expect(observable.setNavigationFailure(error, navigation)).toMatchObject({
    syncStatus: "error",
    error,
    pendingNavigation: navigation,
  });
  expect(observable.setError(error)).toMatchObject({ syncStatus: "error", error });
  expect(observable.advanceVersions(8, 7)).toMatchObject({
    sessionVersion: 8,
    projectionVersion: 7,
  });

  const reset = observable.resetForBootstrap();
  expect(reset).toMatchObject({
    projection: null,
    sessionVersion: null,
    projectionVersion: null,
    eventCursor: 0,
    syncStatus: "bootstrapping",
    pendingBootstrap: null,
    pendingNavigation: null,
  });
});


function projection(): RouteDeckProjection {
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
    event_cursor: 0,
    failure: null,
    interaction: { phase: "idle", owner: null },
    legal_operations: [],
    suggested_actions: [],
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
    projection_version: 1,
    session_version: 1,
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

function event(patch: Partial<RouteDeckEvent> = {}): RouteDeckEvent {
  return {
    created_at: "2030-01-01T00:00:00Z",
    cursor: 1,
    event_id: "event-1",
    event_type: "projection_changed",
    payload: {
      node_id: "home",
      operation_id: null,
      request_id: null,
      status_code: "ready",
      entity_handles: [],
      details: [],
      failure: null,
    },
    projection_version: 1,
    session_version: 1,
    ...patch,
  };
}
