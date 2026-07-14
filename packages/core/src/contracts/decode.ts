import type {
  PublicRouteDeckEvent as GeneratedRouteDeckEvent,
  DeepLinkPolicy,
  DispatchRequest,
  FailureKind,
  FrontendContract,
  FrontendNodeContract,
  OperationDisposition,
  OperationPhase,
  OperationResult,
  OperationSource,
  ProjectedSuggestedAction,
  PrivateFormWriteRequest,
  PublicEntityHandle,
  PublicEventPayload,
  PublicProjection,
  PublicValue,
  ReviewRequest,
  RouteDeckEventType,
  RouteDeckFailure,
} from "./generated";
import { RouteDeckContractError } from "../client/errors";

export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };
export type JsonObject = { [key: string]: JsonValue };

export interface RouteDeckPublicValue extends Omit<PublicValue, "value"> {
  value: JsonValue;
}

export interface RouteDeckPublicEntityHandle
  extends Omit<PublicEntityHandle, "values"> {
  values: RouteDeckPublicValue[];
}

export interface RouteDeckProjectionLocation {
  node_id: string;
  route_params: RouteDeckPublicValue[];
}

export interface RouteDeckProjectedSurface {
  component: string;
  props: RouteDeckPublicValue[];
  surface_id: string;
}

export interface RouteDeckProjectedSurfaceSlots {
  active: RouteDeckProjectedSurface | null;
  detail: RouteDeckProjectedSurface[];
  diagnostic: RouteDeckProjectedSurface[];
  error: RouteDeckProjectedSurface[];
  form: RouteDeckProjectedSurface[];
  frame: RouteDeckProjectedSurface[];
  peer: RouteDeckProjectedSurface[];
  review: RouteDeckProjectedSurface[];
  status: RouteDeckProjectedSurface[];
}

export interface RouteDeckProjectedSuggestedAction
  extends Omit<ProjectedSuggestedAction, "arguments"> {
  arguments: JsonObject;
}

export interface RouteDeckProjection
  extends Omit<
    PublicProjection,
    "current" | "entities" | "navigation" | "suggested_actions" | "surfaces"
  > {
  current: RouteDeckProjectionLocation;
  entities: RouteDeckPublicEntityHandle[];
  navigation: Omit<PublicProjection["navigation"], "current"> & {
    current: RouteDeckProjectionLocation;
  };
  suggested_actions: RouteDeckProjectedSuggestedAction[];
  surfaces: RouteDeckProjectedSurfaceSlots;
}

export interface RouteDeckEventPayload
  extends Omit<PublicEventPayload, "details" | "entity_handles"> {
  details: RouteDeckPublicValue[];
  entity_handles: RouteDeckPublicEntityHandle[];
}

export interface RouteDeckEvent
  extends Omit<
    GeneratedRouteDeckEvent,
    "payload" | "projection_version" | "session_id"
  > {
  payload: RouteDeckEventPayload;
  projection_version: number | null;
}

export type RouteDeckDispatchRequest = DispatchRequest;
export type RouteDeckReviewRequest = ReviewRequest;
export type RouteDeckPrivateFormWriteRequest = PrivateFormWriteRequest;
export type RouteDeckDispatchResult = Omit<OperationResult, "session_id">;

export interface RouteDeckSessionEnvelope {
  projection: RouteDeckProjection;
}

export interface RouteDeckFrontendContractEnvelope {
  frontend_contract: FrontendContract;
}

export interface RouteDeckFailureEnvelope {
  failure: RouteDeckFailure;
}

export interface RouteDeckPrivateFormSnapshot {
  form_id: string;
  revision: number;
  complete: boolean;
  session_version: number;
  value: JsonObject;
}

export interface RouteDeckPrivateFormSaved {
  form_id: string;
  revision: number;
  complete: boolean;
  session_version: number;
  projection_version: number;
}

export interface RouteDeckInspection {
  current_node: string;
  reachable_nodes: string[];
  legal_operations: JsonObject[];
  blocked_operations: JsonObject[];
  guard_explanations: string[];
  capabilities: JsonObject[];
  surfaces: JsonObject;
  route_traces: JsonObject[];
  diagnostics: JsonObject;
}

const EVENT_TYPES = new Set<RouteDeckEventType>([
  "session_created",
  "projection_changed",
  "navigation_changed",
  "operation_changed",
  "private_form_changed",
  "turn_started",
  "turn_finalized",
  "turn_interrupted",
]);
const FAILURE_KINDS = new Set<FailureKind>([
  "contract",
  "state_conflict",
  "context_provider",
  "guard",
  "review",
  "transport",
  "provider_protocol",
  "business",
  "persistence",
  "external_outcome_unknown",
  "internal",
]);
const DISPOSITIONS = new Set<OperationDisposition>([
  "completed",
  "blocked",
  "needs_input",
  "requires_review",
  "pending",
  "failed",
  "external_outcome_unknown",
]);
const OPERATION_SOURCES = new Set<OperationSource>([
  "surface",
  "agent",
  "system",
  "route",
]);
const OPERATION_PHASES = new Set<OperationPhase>([
  "received",
  "lease_acquired",
  "validated",
  "context_refreshed",
  "guards_passed",
  "review_staged",
  "execution_claimed",
  "tool_started",
  "tool_succeeded",
  "tool_failed",
  "tool_outcome_unknown",
  "execution_result_recorded",
  "state_committed",
  "completed",
]);

export function decodeSessionEnvelope(value: unknown): RouteDeckSessionEnvelope {
  const record = expectRecord(value, "$", ["projection"]);
  return { projection: decodeProjection(record.projection, "$.projection") };
}

export function decodeFrontendContractEnvelope(
  value: unknown,
): RouteDeckFrontendContractEnvelope {
  const record = expectRecord(value, "$", ["frontend_contract"]);
  return {
    frontend_contract: decodeFrontendContract(record.frontend_contract),
  };
}

export function decodeProjection(
  value: unknown,
  path = "$",
): RouteDeckProjection {
  const record = expectRecord(
    value,
    path,
    [
      "current",
      "diagnostics",
      "entities",
      "event_cursor",
      "failure",
      "interaction",
      "legal_operations",
      "navigation",
      "projection_version",
      "session_version",
      "status",
      "suggested_actions",
      "surfaces",
    ],
    ["graph_node"],
  );
  const current = decodeLocation(record.current, `${path}.current`);
  if (
    record.graph_node !== undefined &&
    expectString(record.graph_node, `${path}.graph_node`) !== current.node_id
  ) {
    fail(`${path}.graph_node`, "must match current.node_id");
  }
  const navigationRecord = expectRecord(
    record.navigation,
    `${path}.navigation`,
    [
      "current",
      "current_entry_id",
      "route_template",
      "resume_handle",
      "can_back",
      "can_forward",
      "can_cancel",
    ],
    [
      "back_node_id",
      "forward_node_id",
      "cancel_target_node_id",
    ],
  );
  const surfacesRecord = expectRecord(
    record.surfaces,
    `${path}.surfaces`,
    [
      "active",
      "detail",
      "diagnostic",
      "error",
      "form",
      "frame",
      "peer",
      "review",
      "status",
    ],
  );
  const diagnosticsRecord = expectRecord(
    record.diagnostics,
    `${path}.diagnostics`,
    ["schema_version", "navgraph_version", "current_node_id", "declared_provider_ids"],
  );
  const statusRecord = expectRecord(
    record.status,
    `${path}.status`,
    ["code", "message"],
  );
  const interactionRecord = expectRecord(
    record.interaction,
    `${path}.interaction`,
    ["owner", "phase"],
  );
  const interactionPhase = expectEnum(
    interactionRecord.phase,
    `${path}.interaction.phase`,
    new Set(["idle", "active"] as const),
  );
  const interactionOwner =
    interactionRecord.owner === null
      ? null
      : expectEnum(
          interactionRecord.owner,
          `${path}.interaction.owner`,
          new Set(
            ["chat", "surface", "review", "system", "navigation"] as const,
          ),
        );
  if (
    (interactionPhase === "idle" && interactionOwner !== null) ||
    (interactionPhase === "active" && interactionOwner === null)
  ) {
    fail(`${path}.interaction`, "phase and owner do not form a valid interaction state");
  }
  const projection: RouteDeckProjection = {
    current,
    diagnostics: {
      schema_version: expectInteger(
        diagnosticsRecord.schema_version,
        `${path}.diagnostics.schema_version`,
        1,
      ),
      navgraph_version: expectString(
        diagnosticsRecord.navgraph_version,
        `${path}.diagnostics.navgraph_version`,
      ),
      current_node_id: expectString(
        diagnosticsRecord.current_node_id,
        `${path}.diagnostics.current_node_id`,
      ),
      declared_provider_ids: decodeStringArray(
        diagnosticsRecord.declared_provider_ids,
        `${path}.diagnostics.declared_provider_ids`,
      ),
    },
    entities: decodeArray(
      record.entities,
      `${path}.entities`,
      decodeEntity,
    ),
    event_cursor: expectInteger(record.event_cursor, `${path}.event_cursor`, 0),
    failure:
      record.failure === null
        ? null
        : decodeFailure(record.failure, `${path}.failure`),
    interaction: {
      phase: interactionPhase,
      owner: interactionOwner,
    },
    legal_operations: decodeArray(
      record.legal_operations,
      `${path}.legal_operations`,
      (item, itemPath) => {
        const operation = expectRecord(
          item,
          itemPath,
          ["operation_id", "title", "safety_class", "review_required"],
        );
        return {
          operation_id: expectString(operation.operation_id, `${itemPath}.operation_id`),
          title: expectString(operation.title, `${itemPath}.title`, true),
          safety_class: expectString(
            operation.safety_class,
            `${itemPath}.safety_class`,
          ),
          review_required: expectBoolean(
            operation.review_required,
            `${itemPath}.review_required`,
          ),
        };
      },
    ),
    navigation: {
      current: decodeLocation(
        navigationRecord.current,
        `${path}.navigation.current`,
      ),
      current_entry_id: expectInteger(
        navigationRecord.current_entry_id,
        `${path}.navigation.current_entry_id`,
        1,
      ),
      route_template: expectString(
        navigationRecord.route_template,
        `${path}.navigation.route_template`,
      ),
      resume_handle: decodeNullableString(
        navigationRecord.resume_handle,
        `${path}.navigation.resume_handle`,
      ),
      can_back: expectBoolean(navigationRecord.can_back, `${path}.navigation.can_back`),
      can_forward: expectBoolean(
        navigationRecord.can_forward,
        `${path}.navigation.can_forward`,
      ),
      can_cancel: expectBoolean(
        navigationRecord.can_cancel,
        `${path}.navigation.can_cancel`,
      ),
      back_node_id: decodeNullableString(
        navigationRecord.back_node_id,
        `${path}.navigation.back_node_id`,
      ),
      forward_node_id: decodeNullableString(
        navigationRecord.forward_node_id,
        `${path}.navigation.forward_node_id`,
      ),
      cancel_target_node_id: decodeNullableString(
        navigationRecord.cancel_target_node_id,
        `${path}.navigation.cancel_target_node_id`,
      ),
    },
    projection_version: expectInteger(
      record.projection_version,
      `${path}.projection_version`,
      0,
    ),
    session_version: expectInteger(
      record.session_version,
      `${path}.session_version`,
      0,
    ),
    status: {
      code: expectString(statusRecord.code, `${path}.status.code`),
      message: decodeNullableString(statusRecord.message, `${path}.status.message`),
    },
    suggested_actions: decodeArray(
      record.suggested_actions,
      `${path}.suggested_actions`,
      decodeSuggestedAction,
    ),
    surfaces: {
      active:
        surfacesRecord.active === null
          ? null
          : decodeSurface(surfacesRecord.active, `${path}.surfaces.active`),
      detail: decodeSurfaceArray(surfacesRecord.detail, `${path}.surfaces.detail`),
      diagnostic: decodeSurfaceArray(
        surfacesRecord.diagnostic,
        `${path}.surfaces.diagnostic`,
      ),
      error: decodeSurfaceArray(surfacesRecord.error, `${path}.surfaces.error`),
      form: decodeSurfaceArray(surfacesRecord.form, `${path}.surfaces.form`),
      frame: decodeSurfaceArray(surfacesRecord.frame, `${path}.surfaces.frame`),
      peer: decodeSurfaceArray(surfacesRecord.peer, `${path}.surfaces.peer`),
      review: decodeSurfaceArray(surfacesRecord.review, `${path}.surfaces.review`),
      status: decodeSurfaceArray(surfacesRecord.status, `${path}.surfaces.status`),
    },
  };
  if (projection.navigation.current.node_id !== projection.current.node_id) {
    fail(`${path}.navigation.current.node_id`, "must match current.node_id");
  }
  if (projection.diagnostics.current_node_id !== projection.current.node_id) {
    fail(`${path}.diagnostics.current_node_id`, "must match current.node_id");
  }
  if (projection.projection_version > projection.session_version) {
    fail(`${path}.projection_version`, "cannot exceed session_version");
  }
  return projection;
}

export function decodeEvent(value: unknown): RouteDeckEvent {
  const record = expectRecord(
    value,
    "$event",
    [
      "created_at",
      "cursor",
      "event_id",
      "event_type",
      "payload",
      "projection_version",
      "session_version",
    ],
  );
  const eventType = expectEnum(
    record.event_type,
    "$event.event_type",
    EVENT_TYPES,
  );
  const payloadRecord = expectRecord(
    record.payload,
    "$event.payload",
    [
      "node_id",
      "operation_id",
      "request_id",
      "status_code",
      "entity_handles",
      "details",
      "failure",
    ],
  );
  return {
    created_at: expectIsoDate(record.created_at, "$event.created_at"),
    cursor: expectInteger(record.cursor, "$event.cursor", 1),
    event_id: expectString(record.event_id, "$event.event_id"),
    event_type: eventType,
    payload: {
      node_id: decodeNullableString(payloadRecord.node_id, "$event.payload.node_id"),
      operation_id: decodeNullableString(
        payloadRecord.operation_id,
        "$event.payload.operation_id",
      ),
      request_id: decodeNullableString(
        payloadRecord.request_id,
        "$event.payload.request_id",
      ),
      status_code: decodeNullableString(
        payloadRecord.status_code,
        "$event.payload.status_code",
      ),
      entity_handles: decodeArray(
        payloadRecord.entity_handles,
        "$event.payload.entity_handles",
        decodeEntity,
      ),
      details: decodeArray(
        payloadRecord.details,
        "$event.payload.details",
        decodePublicValue,
      ),
      failure:
        payloadRecord.failure === null
          ? null
          : decodeFailure(payloadRecord.failure, "$event.payload.failure"),
    },
    projection_version:
      record.projection_version === null
        ? null
        : expectInteger(record.projection_version, "$event.projection_version", 0),
    session_version: expectInteger(
      record.session_version,
      "$event.session_version",
      0,
    ),
  };
}

export function decodeDispatchResult(value: unknown): RouteDeckDispatchResult {
  const record = expectRecord(
    value,
    "$result",
    [
      "disposition",
      "operation_id",
      "request_id",
      "session_version",
      "projection_version",
      "evidence",
      "review",
      "outcome",
      "failure",
    ],
  );
  const evidence = expectRecord(
    record.evidence,
    "$result.evidence",
    [
      "source",
      "phases",
      "attempt_id",
      "request_fingerprint",
      "delivery_phase",
      "result_id",
      "result_fingerprint",
    ],
  );
  const result: RouteDeckDispatchResult = {
    disposition: expectEnum(
      record.disposition,
      "$result.disposition",
      DISPOSITIONS,
    ),
    operation_id: expectString(record.operation_id, "$result.operation_id"),
    request_id: expectString(record.request_id, "$result.request_id"),
    session_version: expectInteger(
      record.session_version,
      "$result.session_version",
      0,
    ),
    projection_version: expectInteger(
      record.projection_version,
      "$result.projection_version",
      0,
    ),
    evidence: {
      source: expectEnum(evidence.source, "$result.evidence.source", OPERATION_SOURCES),
      phases: decodeArray(
        evidence.phases,
        "$result.evidence.phases",
        (item, itemPath) => expectEnum(item, itemPath, OPERATION_PHASES),
      ),
      attempt_id: expectString(evidence.attempt_id, "$result.evidence.attempt_id"),
      request_fingerprint: expectString(
        evidence.request_fingerprint,
        "$result.evidence.request_fingerprint",
      ),
      delivery_phase:
        evidence.delivery_phase === null
          ? null
          : expectOneOf(
              evidence.delivery_phase,
              "$result.evidence.delivery_phase",
              ["not_sent", "possibly_sent", "response_received"] as const,
            ),
      result_id: decodeNullableString(evidence.result_id, "$result.evidence.result_id"),
      result_fingerprint: decodeNullableString(
        evidence.result_fingerprint,
        "$result.evidence.result_fingerprint",
      ),
    },
    review:
      record.review === null
        ? null
        : decodeReview(record.review, "$result.review"),
    outcome: decodeNullableString(record.outcome, "$result.outcome"),
    failure:
      record.failure === null
        ? null
        : decodeFailure(record.failure, "$result.failure"),
  };
  return result;
}

export function decodeFailureEnvelope(value: unknown): RouteDeckFailureEnvelope {
  const record = expectRecord(value, "$error", ["failure"]);
  return { failure: decodeFailure(record.failure, "$error.failure") };
}

export function decodeFrontendContract(value: unknown): FrontendContract {
  const record = expectRecord(value, "$contract", [
    "name",
    "entry_node_id",
    "nodes",
    "transitions",
    "surfaces",
  ]);
  const nodesRecord = expectRecordMap(record.nodes, "$contract.nodes");
  const surfacesRecord = expectRecordMap(record.surfaces, "$contract.surfaces");
  const nodes: Record<string, FrontendNodeContract> = {};
  for (const [key, rawNode] of Object.entries(nodesRecord)) {
    const node = expectRecord(
      rawNode,
      `$contract.nodes.${key}`,
      ["id", "title", "route_template", "deep_link_policy", "surfaces", "operation_ids"],
    );
    const id = expectString(node.id, `$contract.nodes.${key}.id`);
    if (id !== key) fail(`$contract.nodes.${key}.id`, "must match its map key");
    const slots = expectRecord(
      node.surfaces,
      `$contract.nodes.${key}.surfaces`,
      ["active", "frame", "peer", "detail", "form", "review", "status", "error", "diagnostic"],
    );
    nodes[key] = {
      id,
      title: expectString(node.title, `$contract.nodes.${key}.title`, true),
      route_template: expectString(
        node.route_template,
        `$contract.nodes.${key}.route_template`,
      ),
      deep_link_policy: expectOneOf(
        node.deep_link_policy,
        `$contract.nodes.${key}.deep_link_policy`,
        ["shareable", "session_bound"] as const,
      ) as DeepLinkPolicy,
      surfaces: {
        active: decodeNullableString(
          slots.active,
          `$contract.nodes.${key}.surfaces.active`,
        ),
        frame: decodeStringArray(slots.frame, `$contract.nodes.${key}.surfaces.frame`),
        peer: decodeStringArray(slots.peer, `$contract.nodes.${key}.surfaces.peer`),
        detail: decodeStringArray(slots.detail, `$contract.nodes.${key}.surfaces.detail`),
        form: decodeStringArray(slots.form, `$contract.nodes.${key}.surfaces.form`),
        review: decodeStringArray(slots.review, `$contract.nodes.${key}.surfaces.review`),
        status: decodeStringArray(slots.status, `$contract.nodes.${key}.surfaces.status`),
        error: decodeStringArray(slots.error, `$contract.nodes.${key}.surfaces.error`),
        diagnostic: decodeStringArray(
          slots.diagnostic,
          `$contract.nodes.${key}.surfaces.diagnostic`,
        ),
      },
      operation_ids: decodeStringArray(
        node.operation_ids,
        `$contract.nodes.${key}.operation_ids`,
      ),
    };
  }
  const transitions = decodeArray(
    record.transitions,
    "$contract.transitions",
    (rawTransition, path) => {
      const transition = expectRecord(rawTransition, path, [
        "source",
        "operation_id",
        "outcome",
        "target",
      ]);
      const source = expectString(transition.source, `${path}.source`);
      const target = expectString(transition.target, `${path}.target`);
      if (!(source in nodes)) {
        fail(`${path}.source`, "must identify a declared node");
      }
      if (!(target in nodes)) {
        fail(`${path}.target`, "must identify a declared node");
      }
      return {
        source,
        operation_id: expectString(
          transition.operation_id,
          `${path}.operation_id`,
        ),
        outcome: expectString(transition.outcome, `${path}.outcome`),
        target,
      };
    },
  );
  const surfaces: FrontendContract["surfaces"] = {};
  for (const [key, rawSurface] of Object.entries(surfacesRecord)) {
    const surface = expectRecord(
      rawSurface,
      `$contract.surfaces.${key}`,
      ["id", "component", "lifecycle", "affordances", "public_props_schema"],
    );
    const id = expectString(surface.id, `$contract.surfaces.${key}.id`);
    if (id !== key) fail(`$contract.surfaces.${key}.id`, "must match its map key");
    surfaces[key] = {
      id,
      component: expectString(surface.component, `$contract.surfaces.${key}.component`),
      lifecycle: expectOneOf(
        surface.lifecycle,
        `$contract.surfaces.${key}.lifecycle`,
        ["ephemeral", "stable"] as const,
      ),
      affordances: decodeArray(
        surface.affordances,
        `$contract.surfaces.${key}.affordances`,
        (item, itemPath) => {
          const affordance = expectRecord(
            item,
            itemPath,
            ["id", "event", "operation"],
          );
          return {
            id: expectString(affordance.id, `${itemPath}.id`),
            event: expectString(affordance.event, `${itemPath}.event`),
            operation:
              affordance.operation === null
                ? null
                : {
                    id: expectString(
                      expectRecord(affordance.operation, `${itemPath}.operation`, ["id"]).id,
                      `${itemPath}.operation.id`,
                    ),
                  },
          };
        },
      ),
      public_props_schema: expectJsonObject(
        surface.public_props_schema,
        `$contract.surfaces.${key}.public_props_schema`,
      ),
    };
  }
  const entryNodeId = expectString(record.entry_node_id, "$contract.entry_node_id");
  if (!(entryNodeId in nodes)) fail("$contract.entry_node_id", "must identify a declared node");
  return {
    name: expectString(record.name, "$contract.name"),
    entry_node_id: entryNodeId,
    nodes,
    transitions,
    surfaces,
  };
}

export function decodePrivateFormSnapshot(
  value: unknown,
): RouteDeckPrivateFormSnapshot {
  const record = expectRecord(
    value,
    "$privateForm",
    ["form_id", "revision", "complete", "session_version", "value"],
  );
  return {
    form_id: expectString(record.form_id, "$privateForm.form_id"),
    revision: expectInteger(record.revision, "$privateForm.revision", 0),
    complete: expectBoolean(record.complete, "$privateForm.complete"),
    session_version: expectInteger(
      record.session_version,
      "$privateForm.session_version",
      0,
    ),
    value: expectJsonObject(record.value, "$privateForm.value"),
  };
}

export function decodePrivateFormSaved(value: unknown): RouteDeckPrivateFormSaved {
  const record = expectRecord(
    value,
    "$privateFormSaved",
    [
      "form_id",
      "revision",
      "complete",
      "session_version",
      "projection_version",
    ],
  );
  return {
    form_id: expectString(record.form_id, "$privateFormSaved.form_id"),
    revision: expectInteger(record.revision, "$privateFormSaved.revision", 1),
    complete: expectBoolean(record.complete, "$privateFormSaved.complete"),
    session_version: expectInteger(
      record.session_version,
      "$privateFormSaved.session_version",
      0,
    ),
    projection_version: expectInteger(
      record.projection_version,
      "$privateFormSaved.projection_version",
      0,
    ),
  };
}

export function decodeInspection(value: unknown): RouteDeckInspection {
  const record = expectRecord(
    value,
    "$inspection",
    [
      "current_node",
      "reachable_nodes",
      "legal_operations",
      "blocked_operations",
      "guard_explanations",
      "capabilities",
      "surfaces",
      "route_traces",
      "diagnostics",
    ],
  );
  return {
    current_node: expectString(record.current_node, "$inspection.current_node"),
    reachable_nodes: decodeStringArray(
      record.reachable_nodes,
      "$inspection.reachable_nodes",
    ),
    legal_operations: decodeJsonObjectArray(
      record.legal_operations,
      "$inspection.legal_operations",
    ),
    blocked_operations: decodeJsonObjectArray(
      record.blocked_operations,
      "$inspection.blocked_operations",
    ),
    guard_explanations: decodeStringArray(
      record.guard_explanations,
      "$inspection.guard_explanations",
    ),
    capabilities: decodeJsonObjectArray(
      record.capabilities,
      "$inspection.capabilities",
    ),
    surfaces: expectJsonObject(record.surfaces, "$inspection.surfaces"),
    route_traces: decodeJsonObjectArray(
      record.route_traces,
      "$inspection.route_traces",
    ),
    diagnostics: expectJsonObject(record.diagnostics, "$inspection.diagnostics"),
  };
}

function decodeLocation(value: unknown, path: string): RouteDeckProjectionLocation {
  const record = expectRecord(value, path, ["node_id", "route_params"]);
  return {
    node_id: expectString(record.node_id, `${path}.node_id`),
    route_params: decodeArray(
      record.route_params,
      `${path}.route_params`,
      decodePublicValue,
    ),
  };
}

function decodePublicValue(value: unknown, path: string): RouteDeckPublicValue {
  const record = expectRecord(value, path, ["name", "value"]);
  return {
    name: expectString(record.name, `${path}.name`),
    value: expectJson(record.value, `${path}.value`),
  };
}

function decodeEntity(value: unknown, path: string): RouteDeckPublicEntityHandle {
  const record = expectRecord(value, path, ["entity_kind", "handle", "values"]);
  return {
    entity_kind: expectString(record.entity_kind, `${path}.entity_kind`),
    handle: expectString(record.handle, `${path}.handle`),
    values: decodeArray(record.values, `${path}.values`, decodePublicValue),
  };
}

function decodeSurface(value: unknown, path: string): RouteDeckProjectedSurface {
  const record = expectRecord(value, path, ["surface_id", "component", "props"]);
  return {
    surface_id: expectString(record.surface_id, `${path}.surface_id`),
    component: expectString(record.component, `${path}.component`),
    props: decodeArray(record.props, `${path}.props`, decodePublicValue),
  };
}

function decodeSuggestedAction(
  value: unknown,
  path: string,
): RouteDeckProjectedSuggestedAction {
  const record = expectRecord(
    value,
    path,
    ["action_id", "label", "operation_id", "arguments"],
  );
  return {
    action_id: expectString(record.action_id, `${path}.action_id`),
    label: expectString(record.label, `${path}.label`),
    operation_id: expectString(record.operation_id, `${path}.operation_id`),
    arguments: expectJsonObject(record.arguments, `${path}.arguments`),
  };
}

function decodeSurfaceArray(value: unknown, path: string): RouteDeckProjectedSurface[] {
  return decodeArray(value, path, decodeSurface);
}

function decodeReview(value: unknown, path: string): NonNullable<RouteDeckDispatchResult["review"]> {
  const record = expectRecord(value, path, ["id", "expires_at"]);
  return {
    id: expectString(record.id, `${path}.id`),
    expires_at: expectIsoDate(record.expires_at, `${path}.expires_at`),
  };
}

function decodeFailure(value: unknown, path: string): RouteDeckFailure {
  const record = expectRecord(
    value,
    path,
    [
      "kind",
      "code",
      "phase",
      "correlation_id",
      "operation_id",
      "request_id",
      "public_message",
      "recovery_directive",
      "safe_details",
    ],
  );
  const details = expectRecord(
    record.safe_details,
    `${path}.safe_details`,
    [
      "affected_capability",
      "provider",
      "provider_code",
      "http_status",
      "delivery_phase",
    ],
  );
  return {
    kind: expectEnum(record.kind, `${path}.kind`, FAILURE_KINDS),
    code: expectString(record.code, `${path}.code`),
    phase: expectString(record.phase, `${path}.phase`),
    correlation_id: expectString(record.correlation_id, `${path}.correlation_id`),
    operation_id: decodeNullableString(record.operation_id, `${path}.operation_id`),
    request_id: decodeNullableString(record.request_id, `${path}.request_id`),
    public_message: expectString(record.public_message, `${path}.public_message`, true),
    recovery_directive: decodeNullableString(
      record.recovery_directive,
      `${path}.recovery_directive`,
    ),
    safe_details: {
      affected_capability: decodeNullableString(
        details.affected_capability,
        `${path}.safe_details.affected_capability`,
      ),
      provider: decodeNullableString(details.provider, `${path}.safe_details.provider`),
      provider_code: decodeNullableString(
        details.provider_code,
        `${path}.safe_details.provider_code`,
      ),
      http_status:
        details.http_status === null
          ? null
          : expectInteger(details.http_status, `${path}.safe_details.http_status`, 100),
      delivery_phase:
        details.delivery_phase === null
          ? null
          : expectOneOf(
              details.delivery_phase,
              `${path}.safe_details.delivery_phase`,
              ["not_sent", "possibly_sent", "response_received"] as const,
            ),
    },
  };
}

function expectRecord(
  value: unknown,
  path: string,
  required: readonly string[],
  optional: readonly string[] = [],
): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    fail(path, "expected an object");
  }
  const record = value as Record<string, unknown>;
  for (const key of required) {
    if (!(key in record)) fail(`${path}.${key}`, "is required");
  }
  const allowed = new Set([...required, ...optional]);
  for (const key of Object.keys(record)) {
    if (!allowed.has(key)) fail(`${path}.${key}`, "is not declared by the contract");
  }
  return record;
}

function expectRecordMap(value: unknown, path: string): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    fail(path, "expected an object map");
  }
  return value as Record<string, unknown>;
}

function expectString(value: unknown, path: string, allowEmpty = false): string {
  if (typeof value !== "string" || (!allowEmpty && value.length === 0)) {
    fail(path, allowEmpty ? "expected a string" : "expected a non-empty string");
  }
  return value;
}

function expectBoolean(value: unknown, path: string): boolean {
  if (typeof value !== "boolean") fail(path, "expected a boolean");
  return value;
}

function expectInteger(value: unknown, path: string, minimum: number): number {
  if (!Number.isInteger(value) || (value as number) < minimum) {
    fail(path, `expected an integer >= ${minimum}`);
  }
  return value as number;
}

function expectIsoDate(value: unknown, path: string): string {
  const text = expectString(value, path);
  if (Number.isNaN(Date.parse(text))) fail(path, "expected an ISO date-time string");
  return text;
}

function decodeNullableString(value: unknown, path: string): string | null {
  return value === null ? null : expectString(value, path);
}

function decodeArray<T>(
  value: unknown,
  path: string,
  decode: (item: unknown, path: string) => T,
): T[] {
  if (!Array.isArray(value)) fail(path, "expected an array");
  return value.map((item, index) => decode(item, `${path}[${index}]`));
}

function decodeStringArray(value: unknown, path: string): string[] {
  return decodeArray(value, path, (item, itemPath) => expectString(item, itemPath));
}

function decodeJsonObjectArray(value: unknown, path: string): JsonObject[] {
  return decodeArray(value, path, expectJsonObject);
}

function expectJsonObject(value: unknown, path: string): JsonObject {
  const json = expectJson(value, path);
  if (json === null || Array.isArray(json) || typeof json !== "object") {
    fail(path, "expected a JSON object");
  }
  return json as JsonObject;
}

function expectJson(value: unknown, path: string): JsonValue {
  if (value === null || typeof value === "string" || typeof value === "boolean") {
    return value;
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) fail(path, "JSON numbers must be finite");
    return value;
  }
  if (Array.isArray(value)) {
    return value.map((item, index) => expectJson(item, `${path}[${index}]`));
  }
  if (typeof value === "object") {
    const output: JsonObject = {};
    for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
      output[key] = expectJson(item, `${path}.${key}`);
    }
    return output;
  }
  fail(path, "expected JSON-compatible data");
}

function expectEnum<T extends string>(
  value: unknown,
  path: string,
  values: ReadonlySet<T>,
): T {
  const candidate = expectString(value, path) as T;
  if (!values.has(candidate)) fail(path, "contains an unknown enum value");
  return candidate;
}

function expectOneOf<const T extends readonly string[]>(
  value: unknown,
  path: string,
  values: T,
): T[number] {
  const candidate = expectString(value, path);
  if (!(values as readonly string[]).includes(candidate)) {
    fail(path, `expected one of ${values.join(", ")}`);
  }
  return candidate as T[number];
}

function fail(path: string, expectation: string): never {
  throw new RouteDeckContractError(path, expectation);
}
