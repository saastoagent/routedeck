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
  width: number;
  height: number;
}

const NODE_WIDTH = 184;
const NODE_HEIGHT = 86;
const FAMILY_COLUMN_GAP = 72;
const FAMILY_ROW_GAP = 54;
const ROOT_TO_FAMILIES_GAP = 104;
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
  const layoutNodeIds = orderNodesWithinDepth(orderedNodeIds, depth, edges);
  const sitemap = buildSitemapLayout(contract, layoutNodeIds, root);
  const shifted = sourceNodes.map((node) => ({
    id: node.id,
    label: node.title,
    familyLabel: sitemap.familyLabels.get(node.id) ?? null,
    depth: depth.get(node.id)!,
    ...sitemap.positions.get(node.id)!,
  }));
  return {
    nodes: shifted,
    edges: [...edges],
    width: sitemap.width,
    height: sitemap.height,
  };
}

function buildSitemapLayout(
  contract: FrontendContract,
  orderedNodeIds: readonly string[],
  root: string,
) {
  const families = new Map<string, string[]>();
  for (const nodeId of orderedNodeIds) {
    if (nodeId === root) continue;
    const family = sitemapFamily(contract.nodes[nodeId]!.route_template);
    families.set(family, [...(families.get(family) ?? []), nodeId]);
  }
  const familyEntries = [...families.entries()];
  const columns = Math.max(1, familyEntries.length);
  const contentWidth =
    columns * NODE_WIDTH +
    Math.max(0, columns - 1) * FAMILY_COLUMN_GAP;
  const positions = new Map<string, { x: number; y: number }>([
    [
      root,
      {
        x: PADDING + (contentWidth - NODE_WIDTH) / 2,
        y: PADDING,
      },
    ],
  ]);
  const familyLabels = new Map<string, string>();
  const familyTop = PADDING + NODE_HEIGHT + ROOT_TO_FAMILIES_GAP;
  let longestFamily = 0;
  familyEntries.forEach(([family, nodeIds], column) => {
    longestFamily = Math.max(longestFamily, nodeIds.length);
    nodeIds.forEach((nodeId, row) => {
      positions.set(nodeId, {
        x: PADDING + column * (NODE_WIDTH + FAMILY_COLUMN_GAP),
        y: familyTop + row * (NODE_HEIGHT + FAMILY_ROW_GAP),
      });
      if (row === 0) familyLabels.set(nodeId, family);
    });
  });
  const familyHeight =
    longestFamily === 0
      ? 0
      : longestFamily * NODE_HEIGHT +
        Math.max(0, longestFamily - 1) * FAMILY_ROW_GAP;
  return {
    positions,
    familyLabels,
    width: PADDING * 2 + contentWidth,
    height:
      PADDING * 2 +
      NODE_HEIGHT +
      (familyHeight === 0 ? 0 : ROOT_TO_FAMILIES_GAP + familyHeight),
  };
}

function sitemapFamily(routeTemplate: string): string {
  const firstSegment = routeTemplate
    .split("/")
    .find((segment) => segment.length > 0);
  return firstSegment === undefined ? "/" : `/${firstSegment}`;
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
