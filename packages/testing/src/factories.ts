import type {
  FrontendContract,
  RouteDeckDispatchResult,
  RouteDeckEvent,
  RouteDeckEventType,
  RouteDeckProjection,
} from "@routedeck/core";

export function routeDeckProjectionFixture(options: {
  nodeId?: string;
  routeTemplate?: string;
  routeParams?: Array<{ name: string; value: string }>;
  sessionVersion?: number;
  projectionVersion?: number;
  eventCursor?: number;
  historyEntryId?: number;
} = {}): RouteDeckProjection {
  const nodeId = options.nodeId ?? "home";
  const location = {
    node_id: nodeId,
    route_params: (options.routeParams ?? []).map((parameter) => ({
      name: parameter.name,
      value: parameter.value,
    })),
  };
  return {
    current: location,
    diagnostics: {
      schema_version: 1,
      navgraph_version: "test-navgraph-v1",
      current_node_id: nodeId,
      declared_provider_ids: [],
    },
    entities: [],
    event_cursor: options.eventCursor ?? 0,
    failure: null,
    interaction: { phase: "idle", owner: null },
    legal_operations: [],
    suggested_actions: [],
    navigation: {
      current: location,
      current_entry_id: options.historyEntryId ?? 1,
      route_template: options.routeTemplate ?? "/",
      resume_handle: null,
      can_back: false,
      can_forward: false,
      can_cancel: false,
      back_node_id: null,
      forward_node_id: null,
      cancel_target_node_id: null,
    },
    projection_version: options.projectionVersion ?? 1,
    session_version: options.sessionVersion ?? 1,
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

export function routeDeckEventFixture(options: {
  cursor: number;
  sessionVersion?: number;
  projectionVersion?: number | null;
  eventType?: RouteDeckEventType;
}): RouteDeckEvent {
  return {
    event_id: `event-${options.cursor}`,
    cursor: options.cursor,
    event_type: options.eventType ?? "operation_changed",
    session_version: options.sessionVersion ?? options.cursor + 1,
    projection_version: options.projectionVersion ?? null,
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

export function routeDeckFrontendContractFixture(): FrontendContract {
  const emptySlots = {
    frame: [],
    peer: [],
    detail: [],
    form: [],
    review: [],
    status: [],
    error: [],
    diagnostic: [],
  };
  return {
    name: "test-routedeck-app",
    entry_node_id: "home",
    nodes: {
      home: {
        id: "home",
        title: "Home",
        route_template: "/",
        deep_link_policy: "shareable",
        surfaces: { active: "test.active", ...emptySlots },
        operation_ids: [],
      },
      detail: {
        id: "detail",
        title: "Detail",
        route_template: "/items/{item_handle}",
        deep_link_policy: "shareable",
        surfaces: { active: "test.active", ...emptySlots },
        operation_ids: [],
      },
      secure: {
        id: "secure",
        title: "Secure",
        route_template: "/secure",
        deep_link_policy: "session_bound",
        surfaces: { active: "test.active", ...emptySlots },
        operation_ids: [],
      },
    },
    transitions: [],
    surfaces: {
      "test.active": {
        id: "test.active",
        component: "test.active",
        lifecycle: "stable",
        affordances: [],
        public_props_schema: {},
      },
    },
  };
}

export function routeDeckDispatchResultFixture(): RouteDeckDispatchResult {
  return {
    disposition: "completed",
    operation_id: "test.operation",
    request_id: "request-1",
    session_version: 2,
    projection_version: 1,
    evidence: {
      source: "surface",
      phases: ["received", "completed"],
      attempt_id: "attempt-1",
      request_fingerprint: "fingerprint-1",
      delivery_phase: "response_received",
      result_id: "result-1",
      result_fingerprint: "result-fingerprint-1",
    },
    review: null,
    outcome: "completed",
    failure: null,
  };
}
