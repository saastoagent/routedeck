import { expect, it } from "vitest";

import {
  decodeProjection,
  decodePrivateFormSaved,
  decodePrivateFormSnapshot,
} from "./decode";

it("accepts virtual snapshot revision zero but rejects saved revision zero", () => {
  const snapshot = decodePrivateFormSnapshot({
    form_id: "form-public-1",
    revision: 0,
    complete: false,
    session_version: 1,
    value: {},
  });

  expect(snapshot.revision).toBe(0);
  expect(() =>
    decodePrivateFormSaved({
      form_id: "form-public-1",
      revision: 0,
      complete: false,
      session_version: 1,
      projection_version: 1,
    }),
  ).toThrow(/\$privateFormSaved\.revision/);
});

it("keeps strict decoder failures on the canonical contract barrel", () => {
  expect(() =>
    decodePrivateFormSnapshot({
      form_id: "form-public-1",
      revision: 0,
      complete: false,
      session_version: 1,
      value: {},
      undeclared: true,
    }),
  ).toThrow(/\$privateForm\.undeclared/);
});

it("decodes a conversation-only projection with supervised suggested actions", () => {
  const projection = decodeProjection({
    current: { node_id: "buyer.home", route_params: [] },
    diagnostics: {
      schema_version: 1,
      navgraph_version: "navgraph-1",
      current_node_id: "buyer.home",
      declared_provider_ids: [],
    },
    entities: [],
    event_cursor: 0,
    failure: null,
    interaction: { phase: "idle", owner: null },
    legal_operations: [
      {
        operation_id: "catalog.list",
        title: "Browse products",
        safety_class: "read_external",
        review_required: false,
      },
    ],
    suggested_actions: [
      {
        action_id: "buyer.browse_products",
        label: "Browse products",
        operation_id: "catalog.list",
        arguments: {},
      },
    ],
    navigation: {
      current: { node_id: "buyer.home", route_params: [] },
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
    projection_version: 0,
    session_version: 0,
    status: { code: "ready", message: null },
    surfaces: {
      active: null,
      detail: [],
      diagnostic: [],
      error: [],
      form: [],
      frame: [],
      peer: [],
      review: [],
      status: [],
    },
  });

  expect(projection.surfaces.active).toBeNull();
  expect(
    (
      projection as unknown as {
        suggested_actions: Array<{
          action_id: string;
          operation_id: string;
          arguments: Record<string, unknown>;
        }>;
      }
    ).suggested_actions,
  ).toEqual([
    {
      action_id: "buyer.browse_products",
      label: "Browse products",
      operation_id: "catalog.list",
      arguments: {},
    },
  ]);
});
