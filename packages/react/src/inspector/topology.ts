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
  familyLabel: string | null;
  x: number;
  y: number;
  depth: number;
}

export interface NavGraphTopology {
  nodes: NavGraphLayoutNode[];
  edges: NavGraphInspectorEdge[];
  structuralConnections: Array<{ from: string; to: string }>;
  width: number;
  height: number;
}

const NODE_WIDTH = 184;
const NODE_HEIGHT = 86;
const COLUMN_GAP = 42;
const LAYER_GAP = 72;
const WRAPPED_ROW_GAP = 28;
const MAX_COLUMNS_PER_ROW = 6;
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
    return {
      nodes: [],
      edges: [...edges],
      structuralConnections: [],
      width: 0,
      height: 0,
    };
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
  const structuralConnections: Array<{ from: string; to: string }> = [];
  const orderedNodeIds = [root];
  const queue = [root];
  while (queue.length > 0) {
    const current = queue.shift()!;
    const nextDepth = depth.get(current)! + 1;
    for (const target of outgoing.get(current) ?? []) {
      if (depth.has(target)) continue;
      depth.set(target, nextDepth);
      structuralConnections.push({ from: current, to: target });
      orderedNodeIds.push(target);
      queue.push(target);
    }
  }
  const detachedDepth = Math.max(...depth.values()) + 1;
  for (const node of sourceNodes) {
    if (!depth.has(node.id)) {
      depth.set(node.id, detachedDepth);
      orderedNodeIds.push(node.id);
    }
  }
  const layoutNodeIds = orderNodesWithinDepth(orderedNodeIds, depth, edges);
  const sitemap = buildLayeredSitemapLayout(layoutNodeIds, depth, edges);
  const shifted = sourceNodes.map((node) => ({
    id: node.id,
    label: node.title,
    familyLabel: null,
    depth: depth.get(node.id)!,
    ...sitemap.positions.get(node.id)!,
  }));
  return {
    nodes: shifted,
    edges: [...edges],
    structuralConnections,
    width: sitemap.width,
    height: sitemap.height,
  };
}

function buildLayeredSitemapLayout(
  orderedNodeIds: readonly string[],
  depth: ReadonlyMap<string, number>,
  edges: readonly NavGraphInspectorEdge[],
) {
  const layers = new Map<number, string[]>();
  for (const nodeId of orderedNodeIds) {
    const nodeDepth = depth.get(nodeId)!;
    layers.set(nodeDepth, [...(layers.get(nodeDepth) ?? []), nodeId]);
  }
  const orderedLayers = [...layers.entries()].sort(([left], [right]) => left - right);
  const precedingOrder = new Map<string, number>();
  for (const [, layer] of orderedLayers) {
    layer.sort((left, right) => {
      const leftBarycenter = incomingBarycenter(left, edges, precedingOrder);
      const rightBarycenter = incomingBarycenter(right, edges, precedingOrder);
      return leftBarycenter - rightBarycenter || left.localeCompare(right);
    });
    layer.forEach((nodeId, index) => precedingOrder.set(nodeId, index));
  }
  const widestRow = Math.max(
    1,
    ...orderedLayers.map(([, layer]) => Math.min(layer.length, MAX_COLUMNS_PER_ROW)),
  );
  const contentWidth =
    widestRow * NODE_WIDTH + Math.max(0, widestRow - 1) * COLUMN_GAP;
  const positions = new Map<string, { x: number; y: number }>();
  let y = PADDING;
  for (const [, layer] of orderedLayers) {
    const rows = chunk(layer, MAX_COLUMNS_PER_ROW);
    rows.forEach((row, rowIndex) => {
      const rowWidth =
        row.length * NODE_WIDTH + Math.max(0, row.length - 1) * COLUMN_GAP;
      const rowLeft = PADDING + (contentWidth - rowWidth) / 2;
      row.forEach((nodeId, column) => {
        positions.set(nodeId, {
          x: rowLeft + column * (NODE_WIDTH + COLUMN_GAP),
          y: y + rowIndex * (NODE_HEIGHT + WRAPPED_ROW_GAP),
        });
      });
    });
    y +=
      rows.length * NODE_HEIGHT +
      Math.max(0, rows.length - 1) * WRAPPED_ROW_GAP +
      LAYER_GAP;
  }
  return {
    positions,
    width: PADDING * 2 + contentWidth,
    height: Math.max(0, y - LAYER_GAP + PADDING),
  };
}

function incomingBarycenter(
  nodeId: string,
  edges: readonly NavGraphInspectorEdge[],
  precedingOrder: ReadonlyMap<string, number>,
): number {
  const positions = edges
    .filter((edge) => edge.to === nodeId)
    .map((edge) => precedingOrder.get(edge.from))
    .filter((value): value is number => value !== undefined);
  if (positions.length === 0) return Number.MAX_SAFE_INTEGER;
  return positions.reduce((total, value) => total + value, 0) / positions.length;
}

function chunk<T>(values: readonly T[], size: number): T[][] {
  const rows: T[][] = [];
  for (let index = 0; index < values.length; index += size) {
    rows.push(values.slice(index, index + size));
  }
  return rows;
}

function orderNodesWithinDepth(
  nodeIds: readonly string[],
  depth: ReadonlyMap<string, number>,
  edges: readonly NavGraphInspectorEdge[],
): string[] {
  const layers = new Map<number, string[]>();
  for (const nodeId of nodeIds) {
    const nodeDepth = depth.get(nodeId)!;
    layers.set(nodeDepth, [...(layers.get(nodeDepth) ?? []), nodeId]);
  }
  const ordered: string[] = [];
  for (const [, layer] of [...layers.entries()].sort(
    ([left], [right]) => left - right,
  )) {
    const layerIds = new Set(layer);
    const outgoing = new Map(layer.map((nodeId) => [nodeId, new Set<string>()]));
    const indegree = new Map(layer.map((nodeId) => [nodeId, 0]));
    for (const edge of edges) {
      if (
        edge.from === edge.to ||
        !layerIds.has(edge.from) ||
        !layerIds.has(edge.to) ||
        outgoing.get(edge.from)!.has(edge.to)
      ) {
        continue;
      }
      outgoing.get(edge.from)!.add(edge.to);
      indegree.set(edge.to, indegree.get(edge.to)! + 1);
    }
    const remaining = new Set(layer);
    while (remaining.size > 0) {
      const next = layer.find(
        (nodeId) => remaining.has(nodeId) && indegree.get(nodeId) === 0,
      );
      if (next === undefined) {
        ordered.push(...layer.filter((nodeId) => remaining.has(nodeId)));
        break;
      }
      ordered.push(next);
      remaining.delete(next);
      for (const target of outgoing.get(next)!) {
        indegree.set(target, indegree.get(target)! - 1);
      }
    }
  }
  return ordered;
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

export function bundleNavGraphEdges(
  edges: readonly NavGraphInspectorEdge[],
): NavGraphInspectorEdge[] {
  const bundles = new Map<
    string,
    { from: string; to: string; edges: NavGraphInspectorEdge[] }
  >();
  for (const edge of edges) {
    const key = JSON.stringify([edge.from, edge.to]);
    const bundle = bundles.get(key);
    if (bundle === undefined) {
      bundles.set(key, { from: edge.from, to: edge.to, edges: [edge] });
    } else {
      bundle.edges.push(edge);
    }
  }
  return [...bundles.values()].map((bundle) => {
    const first = bundle.edges[0]!;
    return {
      id: `bundle:${first.id}`,
      from: bundle.from,
      to: bundle.to,
      ...(bundle.edges.length === 1
        ? first.label === undefined
          ? {}
          : { label: first.label }
        : { label: `${bundle.edges.length} transitions` }),
    };
  });
}

function compareNodes(
  left: FrontendContract["nodes"][string],
  right: FrontendContract["nodes"][string],
) {
  return left.title.localeCompare(right.title) || left.id.localeCompare(right.id);
}

export const NAVGRAPH_NODE_WIDTH = NODE_WIDTH;
export const NAVGRAPH_NODE_HEIGHT = NODE_HEIGHT;
