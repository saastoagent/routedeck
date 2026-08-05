import type {
  OperationSource,
  ProjectedSuggestedAction,
  PublicEntityHandle,
  PublicProjection,
  PublicValue,
} from "./generated";
import { generatedObjectDescriptors } from "./generatedRuntime";
import type { JsonObject, JsonValue } from "./json";
import strictJsonDecoders from "./json";
import operationDecoders, { decodeOperationSource } from "./operations";

const {
  decodeArray,
  decodeNullableString,
  decodeStringArray,
  expectBoolean,
  expectEnum,
  expectInteger,
  expectJson,
  expectJsonObject,
  expectRecord,
  expectString,
  fail,
} = strictJsonDecoders;
const { decodeFailure } = operationDecoders;

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

export interface RouteDeckSessionEnvelope {
  projection: RouteDeckProjection;
}

export function decodeSessionEnvelope(value: unknown): RouteDeckSessionEnvelope {
  const record = expectRecord(value, "$", generatedObjectDescriptors.SessionEnvelope);
  return { projection: decodeProjection(record.projection, "$.projection") };
}

export function decodeProjection(
  value: unknown,
  path = "$",
): RouteDeckProjection {
  const record = expectRecord(
    value,
    path,
    generatedObjectDescriptors.PublicProjectionResponse,
  );
  const current = decodeLocation(record.current, `${path}.current`);
  if (
    record.graph_node !== undefined &&
    record.graph_node !== null &&
    expectString(record.graph_node, `${path}.graph_node`) !== current.node_id
  ) {
    fail(`${path}.graph_node`, "must match current.node_id");
  }
  const navigationRecord = expectRecord(
    record.navigation,
    `${path}.navigation`,
    generatedObjectDescriptors.ProjectedNavigation,
  );
  const surfacesRecord = expectRecord(
    record.surfaces,
    `${path}.surfaces`,
    generatedObjectDescriptors.ProjectedSurfaceSlots,
  );
  const diagnosticsRecord = expectRecord(
    record.diagnostics,
    `${path}.diagnostics`,
    generatedObjectDescriptors.ProjectionDiagnostics,
  );
  const statusRecord = expectRecord(
    record.status,
    `${path}.status`,
    generatedObjectDescriptors.ProjectionStatus,
  );
  const interactionRecord = expectRecord(
    record.interaction,
    `${path}.interaction`,
    generatedObjectDescriptors.RouteDeckInteractionState,
  );
  const interactionPhase = expectEnum(
    interactionRecord.phase === undefined ? "idle" : interactionRecord.phase,
    `${path}.interaction.phase`,
    new Set(["idle", "active"] as const),
  );
  const interactionOwner =
    interactionRecord.owner === undefined || interactionRecord.owner === null
      ? null
      : expectEnum(
          interactionRecord.owner,
          `${path}.interaction.owner`,
          new Set(
            ["chat", "surface", "review", "system", "navigation"] as const,
          ),
        );
  const interactionRequestId = decodeNullableString(
    interactionRecord.request_id === undefined ? null : interactionRecord.request_id,
    `${path}.interaction.request_id`,
  );
  if (
    (interactionPhase === "idle" &&
      (interactionOwner !== null || interactionRequestId !== null)) ||
    (interactionPhase === "active" &&
      (interactionOwner === null || interactionRequestId === null))
  ) {
    fail(
      `${path}.interaction`,
      "phase, owner, and request_id do not form a valid interaction state",
    );
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
        diagnosticsRecord.declared_provider_ids === undefined
          ? []
          : diagnosticsRecord.declared_provider_ids,
        `${path}.diagnostics.declared_provider_ids`,
      ),
    },
    entities: decodeArray(record.entities, `${path}.entities`, decodeEntity),
    event_cursor: expectInteger(record.event_cursor, `${path}.event_cursor`, 0),
    failure:
      record.failure === undefined || record.failure === null
        ? null
        : decodeFailure(record.failure, `${path}.failure`),
    interaction: {
      phase: interactionPhase,
      owner: interactionOwner,
      request_id: interactionRequestId,
    },
    legal_operations: decodeArray(
      record.legal_operations,
      `${path}.legal_operations`,
      (item, itemPath) => {
        const operation = expectRecord(
          item,
          itemPath,
          generatedObjectDescriptors.ProjectedOperation,
        );
        const allowedSources = decodeArray(
          operation.allowed_sources,
          `${itemPath}.allowed_sources`,
          decodeOperationSource,
        );
        if (allowedSources.length === 0) {
          fail(`${itemPath}.allowed_sources`, "must contain at least one source");
        }
        return {
          operation_id: expectString(operation.operation_id, `${itemPath}.operation_id`),
          title: expectString(operation.title, `${itemPath}.title`, true),
          safety_class: expectString(
            operation.safety_class,
            `${itemPath}.safety_class`,
          ),
          allowed_sources: allowedSources as [OperationSource, ...OperationSource[]],
          review_required: expectBoolean(
            operation.review_required === undefined
              ? false
              : operation.review_required,
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
        navigationRecord.back_node_id === undefined
          ? null
          : navigationRecord.back_node_id,
        `${path}.navigation.back_node_id`,
      ),
      forward_node_id: decodeNullableString(
        navigationRecord.forward_node_id === undefined
          ? null
          : navigationRecord.forward_node_id,
        `${path}.navigation.forward_node_id`,
      ),
      cancel_target_node_id: decodeNullableString(
        navigationRecord.cancel_target_node_id === undefined
          ? null
          : navigationRecord.cancel_target_node_id,
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
      code: expectString(
        statusRecord.code === undefined ? "ready" : statusRecord.code,
        `${path}.status.code`,
      ),
      message: decodeNullableString(
        statusRecord.message === undefined ? null : statusRecord.message,
        `${path}.status.message`,
      ),
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
      detail: decodeSurfaceArray(
        surfacesRecord.detail === undefined ? [] : surfacesRecord.detail,
        `${path}.surfaces.detail`,
      ),
      diagnostic: decodeSurfaceArray(
        surfacesRecord.diagnostic === undefined ? [] : surfacesRecord.diagnostic,
        `${path}.surfaces.diagnostic`,
      ),
      error: decodeSurfaceArray(
        surfacesRecord.error === undefined ? [] : surfacesRecord.error,
        `${path}.surfaces.error`,
      ),
      form: decodeSurfaceArray(
        surfacesRecord.form === undefined ? [] : surfacesRecord.form,
        `${path}.surfaces.form`,
      ),
      frame: decodeSurfaceArray(
        surfacesRecord.frame === undefined ? [] : surfacesRecord.frame,
        `${path}.surfaces.frame`,
      ),
      peer: decodeSurfaceArray(
        surfacesRecord.peer === undefined ? [] : surfacesRecord.peer,
        `${path}.surfaces.peer`,
      ),
      review: decodeSurfaceArray(
        surfacesRecord.review === undefined ? [] : surfacesRecord.review,
        `${path}.surfaces.review`,
      ),
      status: decodeSurfaceArray(
        surfacesRecord.status === undefined ? [] : surfacesRecord.status,
        `${path}.surfaces.status`,
      ),
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

function decodeLocation(value: unknown, path: string): RouteDeckProjectionLocation {
  const record = expectRecord(
    value,
    path,
    generatedObjectDescriptors.ProjectionLocation,
  );
  return {
    node_id: expectString(record.node_id, `${path}.node_id`),
    route_params: decodeArray(
      record.route_params === undefined ? [] : record.route_params,
      `${path}.route_params`,
      decodePublicValue,
    ),
  };
}

function decodePublicValue(value: unknown, path: string): RouteDeckPublicValue {
  const record = expectRecord(value, path, generatedObjectDescriptors.PublicValue);
  return {
    name: expectString(record.name, `${path}.name`),
    value: expectJson(record.value, `${path}.value`),
  };
}

function decodeEntity(value: unknown, path: string): RouteDeckPublicEntityHandle {
  const record = expectRecord(
    value,
    path,
    generatedObjectDescriptors.PublicEntityHandle,
  );
  return {
    entity_kind: expectString(record.entity_kind, `${path}.entity_kind`),
    handle: expectString(record.handle, `${path}.handle`),
    values: decodeArray(
      record.values === undefined ? [] : record.values,
      `${path}.values`,
      decodePublicValue,
    ),
  };
}

function decodeSurface(value: unknown, path: string): RouteDeckProjectedSurface {
  const record = expectRecord(
    value,
    path,
    generatedObjectDescriptors.ProjectedSurface,
  );
  return {
    surface_id: expectString(record.surface_id, `${path}.surface_id`),
    component: expectString(record.component, `${path}.component`),
    props: decodeArray(
      record.props === undefined ? [] : record.props,
      `${path}.props`,
      decodePublicValue,
    ),
  };
}

function decodeSuggestedAction(
  value: unknown,
  path: string,
): RouteDeckProjectedSuggestedAction {
  const record = expectRecord(
    value,
    path,
    generatedObjectDescriptors.ProjectedSuggestedAction,
  );
  return {
    action_id: expectString(record.action_id, `${path}.action_id`),
    label: expectString(record.label, `${path}.label`),
    operation_id: expectString(record.operation_id, `${path}.operation_id`),
    arguments: expectJsonObject(
      record.arguments === undefined ? {} : record.arguments,
      `${path}.arguments`,
    ),
  };
}

function decodeSurfaceArray(value: unknown, path: string): RouteDeckProjectedSurface[] {
  return decodeArray(value, path, decodeSurface);
}

const projectionDecoders = Object.freeze({ decodeEntity, decodePublicValue });

export default projectionDecoders;
