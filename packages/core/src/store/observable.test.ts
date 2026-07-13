import { expect, test } from "vitest";

import type { RouteDeckProjection } from "../contracts/decode";
import { RouteDeckObservableState } from "./observable";


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
