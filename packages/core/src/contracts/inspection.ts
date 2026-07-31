import type { JsonObject } from "./json";
import { generatedObjectDescriptors } from "./generatedRuntime";
import strictJsonDecoders from "./json";

const {
  decodeJsonObjectArray,
  decodeStringArray,
  expectJsonObject,
  expectRecord,
  expectString,
} = strictJsonDecoders;

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
  agent_context: JsonObject | null;
}

export function decodeInspection(value: unknown): RouteDeckInspection {
  const record = expectRecord(
    value,
    "$inspection",
    generatedObjectDescriptors.InspectionPayload,
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
    agent_context:
      record.agent_context === null
        ? null
        : expectJsonObject(record.agent_context, "$inspection.agent_context"),
  };
}
