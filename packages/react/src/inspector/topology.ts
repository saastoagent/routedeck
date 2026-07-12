import { RouteDeckStateError, type FrontendContract, type JsonObject } from "@routedeck/core";

export interface NavGraphInspectorEdge {
  id: string;
  from: string;
  to: string;
  label?: string;
}

export interface NavGraphLayoutNode {
  id: string;
  label: string;
  x: number;
  y: number;
  depth: number;
}

export interface NavGraphTopology {
  nodes: NavGraphLayoutNode[];
  edges: NavGraphInspectorEdge[];
  width: number;
  height: number;
}

const NODE_WIDTH = 184;
const NODE_HEIGHT = 86;
const COLUMN_GAP = 84;
const ROW_GAP = 78;
const PADDING = 56;

export function buildNavGraphTopology(
  contract: FrontendContract,
  edges: readonly NavGraphInspectorEdge[],
): NavGraphTopology {
  const sourceNodes = Object.values(contract.nodes).sort(compareNodes);
  const nodeIds = new Set(sourceNodes.map((node) => node.id));
  for (const edge of edges) {
    if (!nodeIds.has(edge.from) || !nodeIds.has(edge.to)) {
      throw new RouteDeckStateError(
        "inspector_edge_dangles",
        `Inspector edge ${edge.id} references an undeclared node.`,
      );
    }
  }
  if (sourceNodes.length === 0) {
    return { nodes: [], edges: [...edges], width: 0, height: 0 };
  }

  const root = nodeIds.has(contract.entry_node_id)
    ? contract.entry_node_id
    : sourceNodes[0]!.id;
  const outgoing = new Map<string, string[]>(
    sourceNodes.map((node) => [node.id, []]),
  );
  for (const edge of edges) outgoing.get(edge.from)!.push(edge.to);
  for (const values of outgoing.values()) values.sort();

  const depth = new Map<string, number>([[root, 0]]);
  const orderedNodeIds = [root];
  const queue = [root];
  while (queue.length > 0) {
    const current = queue.shift()!;
    const nextDepth = depth.get(current)! + 1;
    for (const target of outgoing.get(current) ?? []) {
      if (depth.has(target)) continue;
      depth.set(target, nextDepth);
      orderedNodeIds.push(target);
      queue.push(target);
    }
  }
  let detachedDepth = Math.max(...depth.values()) + 1;
  for (const node of sourceNodes) {
    if (!depth.has(node.id)) {
      depth.set(node.id, detachedDepth++);
      orderedNodeIds.push(node.id);
    }
  }
  const columns = Math.min(
    4,
    Math.max(1, Math.ceil(Math.sqrt(orderedNodeIds.length * 1.5))),
  );
  const positions = new Map<string, { x: number; y: number }>();
  orderedNodeIds.forEach((nodeId, index) => {
    const row = Math.floor(index / columns);
    const positionInRow = index % columns;
    const column = row % 2 === 0 ? positionInRow : columns - 1 - positionInRow;
    positions.set(nodeId, {
      x: PADDING + column * (NODE_WIDTH + COLUMN_GAP),
      y: PADDING + row * (NODE_HEIGHT + ROW_GAP),
    });
  });
  const shifted = sourceNodes.map((node) => ({
    id: node.id,
    label: node.title,
    depth: depth.get(node.id)!,
    ...positions.get(node.id)!,
  }));
  const rows = Math.ceil(orderedNodeIds.length / columns);
  return {
    nodes: shifted,
    edges: [...edges],
    width:
      PADDING * 2 + columns * NODE_WIDTH + Math.max(0, columns - 1) * COLUMN_GAP,
    height:
      PADDING * 2 + rows * NODE_HEIGHT + Math.max(0, rows - 1) * ROW_GAP,
  };
}

export function navGraphEdgesFromRouteTraces(
  traces: readonly JsonObject[],
): NavGraphInspectorEdge[] {
  return traces.map((trace, index) => {
    const from = trace.source ?? trace.from;
    const to = trace.target ?? trace.to;
    const rawId = trace.id;
    const rawOperation = trace.operation_id;
    const rawOutcome = trace.outcome;
    const rawLabel =
      trace.label ??
      (typeof rawOperation === "string" && typeof rawOutcome === "string"
        ? `${rawOperation} · ${rawOutcome}`
        : undefined);
    if (typeof from !== "string" || typeof to !== "string") {
      throw new RouteDeckStateError(
        "invalid_route_trace",
        `Route trace ${index} must declare string from and to nodes.`,
      );
    }
    return {
      id: typeof rawId === "string" ? rawId : `${from}->${to}:${index}`,
      from,
      to,
      ...(typeof rawLabel === "string" ? { label: rawLabel } : {}),
    };
  });
}

export function navGraphEdgesFromContract(
  contract: FrontendContract,
): NavGraphInspectorEdge[] {
  return contract.transitions.map((transition, index) => ({
    id: `${transition.source}->${transition.target}:${transition.operation_id}:${transition.outcome}:${index}`,
    from: transition.source,
    to: transition.target,
    label: `${transition.operation_id} · ${transition.outcome}`,
  }));
}

function compareNodes(
  left: FrontendContract["nodes"][string],
  right: FrontendContract["nodes"][string],
) {
  return left.title.localeCompare(right.title) || left.id.localeCompare(right.id);
}

export const NAVGRAPH_NODE_WIDTH = NODE_WIDTH;
export const NAVGRAPH_NODE_HEIGHT = NODE_HEIGHT;
