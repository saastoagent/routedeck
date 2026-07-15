import type {
  DeepLinkPolicy,
  FrontendContract,
  FrontendNodeContract,
} from "./generated";
import strictJsonDecoders from "./json";

const {
  decodeArray,
  decodeNullableString,
  decodeStringArray,
  expectJsonObject,
  expectOneOf,
  expectRecord,
  expectRecordMap,
  expectString,
  fail,
} = strictJsonDecoders;

export interface RouteDeckFrontendContractEnvelope {
  frontend_contract: FrontendContract;
}

export function decodeFrontendContractEnvelope(
  value: unknown,
): RouteDeckFrontendContractEnvelope {
  const record = expectRecord(value, "$", ["frontend_contract"]);
  return {
    frontend_contract: decodeFrontendContract(record.frontend_contract),
  };
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
  if (!(entryNodeId in nodes)) {
    fail("$contract.entry_node_id", "must identify a declared node");
  }
  return {
    name: expectString(record.name, "$contract.name"),
    entry_node_id: entryNodeId,
    nodes,
    transitions,
    surfaces,
  };
}
