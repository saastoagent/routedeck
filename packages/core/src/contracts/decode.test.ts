import { expect, it } from "vitest";

import {
  decodeProjection,
  decodePrivateFormSaved,
  decodePrivateFormSnapshot,
} from "./decode";
import {
  generatedObjectDescriptors,
  type GeneratedObjectDescriptor,
} from "./generatedRuntime";
import strictJsonDecoders from "./json";

const { expectRecord } = strictJsonDecoders;

function expectContractKeys(
  value: object,
  descriptor: GeneratedObjectDescriptor,
  omitted: readonly string[] = [],
): void {
  const expected = [...descriptor.required, ...descriptor.optional]
    .filter((key) => !omitted.includes(key))
    .sort();
  expect(Object.keys(value).sort()).toEqual(expected);
}

it("clones mutable generated defaults for every decoded record", () => {
  const firstSlots = expectRecord(
    { active: null },
    "$firstSlots",
    generatedObjectDescriptors.ProjectedSurfaceSlots,
  );
  const secondSlots = expectRecord(
    { active: null },
    "$secondSlots",
    generatedObjectDescriptors.ProjectedSurfaceSlots,
  );
  (firstSlots.detail as unknown[]).push("mutated");

  expect(secondSlots.detail).toEqual([]);
  expect(generatedObjectDescriptors.ProjectedSurfaceSlots.defaults.detail).toEqual(
    [],
  );

  const explicitUndefined = expectRecord(
    { active: null, detail: undefined },
    "$explicitUndefined",
    generatedObjectDescriptors.ProjectedSurfaceSlots,
  );
  const explicitNull = expectRecord(
    { active: null, detail: null },
    "$explicitNull",
    generatedObjectDescriptors.ProjectedSurfaceSlots,
  );
  expect(explicitUndefined.detail).toBeUndefined();
  expect(explicitNull.detail).toBeNull();
});

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
    interaction: {
      phase: "active",
      owner: "chat",
      request_id: "entry-turn-1",
    },
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
  expect(projection.interaction.request_id).toBe("entry-turn-1");
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

it("accepts the minimum Python-declared PublicProjection payload", () => {
  const projection = decodeProjection({
    current: { node_id: "buyer.home" },
    diagnostics: {
      schema_version: 1,
      navgraph_version: "navgraph-1",
      current_node_id: "buyer.home",
    },
    entities: [{ entity_kind: "catalog", handle: "entity-public-1" }],
    event_cursor: 0,
    interaction: {},
    legal_operations: [
      {
        operation_id: "catalog.list",
        title: "Browse products",
        safety_class: "read_external",
      },
    ],
    navigation: {
      current: { node_id: "buyer.home" },
      current_entry_id: 1,
      route_template: "/",
      resume_handle: null,
      can_back: false,
      can_forward: false,
      can_cancel: false,
    },
    projection_version: 0,
    session_version: 0,
    status: {},
    suggested_actions: [
      {
        action_id: "buyer.browse_products",
        label: "Browse products",
        operation_id: "catalog.list",
      },
    ],
    surfaces: {
      active: {
        surface_id: "buyer.home",
        component: "BuyerHome",
      },
    },
  });

  expect(projection).toMatchObject({
    failure: null,
    interaction: { owner: null, phase: "idle", request_id: null },
    status: { code: "ready", message: null },
  });
  expect(projection.current.route_params).toEqual([]);
  expect(projection.entities[0]?.values).toEqual([]);
  expect(projection.legal_operations[0]?.review_required).toBe(false);
  expect(projection.suggested_actions[0]?.arguments).toEqual({});
  expect(projection.surfaces.active?.props).toEqual([]);
  expect(projection.surfaces.detail).toEqual([]);
});

it("accepts and retains the maximum Python-declared PublicProjection payload", () => {
  const projection = decodeProjection({
    current: {
      node_id: "buyer.home",
      route_params: [{ name: "section", value: "featured" }],
    },
    diagnostics: {
      schema_version: 1,
      navgraph_version: "navgraph-1",
      current_node_id: "buyer.home",
      declared_provider_ids: ["catalog.provider"],
    },
    entities: [
      {
        entity_kind: "catalog",
        handle: "entity-public-1",
        values: [{ name: "title", value: "Featured" }],
      },
    ],
    event_cursor: 1,
    failure: null,
    graph_node: "buyer.home",
    interaction: {
      owner: "chat",
      phase: "active",
      request_id: "entry-turn-1",
    },
    legal_operations: [
      {
        operation_id: "catalog.list",
        title: "Browse products",
        safety_class: "read_external",
        review_required: false,
      },
    ],
    navigation: {
      current: {
        node_id: "buyer.home",
        route_params: [{ name: "section", value: "featured" }],
      },
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
    suggested_actions: [
      {
        action_id: "buyer.browse_products",
        label: "Browse products",
        operation_id: "catalog.list",
        arguments: { query: "featured" },
      },
    ],
    surfaces: {
      active: {
        surface_id: "buyer.home",
        component: "BuyerHome",
        props: [{ name: "title", value: "Featured" }],
      },
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

  expect(projection.interaction.request_id).toBe("entry-turn-1");
  expectContractKeys(
    projection,
    generatedObjectDescriptors.PublicProjectionResponse,
    ["graph_node"],
  );
  expectContractKeys(
    projection.interaction,
    generatedObjectDescriptors.RouteDeckInteractionState,
  );
  expectContractKeys(
    projection.navigation,
    generatedObjectDescriptors.ProjectedNavigation,
  );
  expectContractKeys(
    projection.current,
    generatedObjectDescriptors.ProjectionLocation,
  );
  expectContractKeys(
    projection.diagnostics,
    generatedObjectDescriptors.ProjectionDiagnostics,
  );
  expectContractKeys(projection.status, generatedObjectDescriptors.ProjectionStatus);
  expectContractKeys(
    projection.legal_operations[0]!,
    generatedObjectDescriptors.ProjectedOperation,
  );
  expectContractKeys(
    projection.suggested_actions[0]!,
    generatedObjectDescriptors.ProjectedSuggestedAction,
  );
  expectContractKeys(
    projection.entities[0]!,
    generatedObjectDescriptors.PublicEntityHandle,
  );
  expectContractKeys(
    projection.surfaces,
    generatedObjectDescriptors.ProjectedSurfaceSlots,
  );
  expectContractKeys(
    projection.surfaces.active!,
    generatedObjectDescriptors.ProjectedSurface,
  );
});

it("rejects idle interaction with a request_id", () => {
  const payload = {
    current: { node_id: "buyer.home" },
    diagnostics: {
      schema_version: 1,
      navgraph_version: "navgraph-1",
      current_node_id: "buyer.home",
    },
    entities: [],
    event_cursor: 0,
    interaction: { phase: "idle", owner: null, request_id: "stale-request" },
    legal_operations: [],
    navigation: {
      current: { node_id: "buyer.home" },
      current_entry_id: 1,
      route_template: "/",
      resume_handle: null,
      can_back: false,
      can_forward: false,
      can_cancel: false,
    },
    projection_version: 0,
    session_version: 0,
    status: {},
    suggested_actions: [],
    surfaces: { active: null },
  };

  expect(() => decodeProjection(payload)).toThrow(/\$\.interaction/);
});

it("rejects active interaction without a request_id", () => {
  const payload = {
    current: { node_id: "buyer.home" },
    diagnostics: {
      schema_version: 1,
      navgraph_version: "navgraph-1",
      current_node_id: "buyer.home",
    },
    entities: [],
    event_cursor: 0,
    interaction: { phase: "active", owner: "chat", request_id: null },
    legal_operations: [],
    navigation: {
      current: { node_id: "buyer.home" },
      current_entry_id: 1,
      route_template: "/",
      resume_handle: null,
      can_back: false,
      can_forward: false,
      can_cancel: false,
    },
    projection_version: 0,
    session_version: 0,
    status: {},
    suggested_actions: [],
    surfaces: { active: null },
  };

  expect(() => decodeProjection(payload)).toThrow(/\$\.interaction/);
});
