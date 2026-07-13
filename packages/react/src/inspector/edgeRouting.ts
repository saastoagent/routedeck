import type { NavGraphInspectorEdge, NavGraphLayoutNode } from "./topology";
import { NAVGRAPH_NODE_HEIGHT, NAVGRAPH_NODE_WIDTH } from "./topology";

export type NavGraphNodeSide = "top" | "right" | "bottom" | "left";

export interface NavGraphEdgeRoute {
  id: string;
  source: { x: number; y: number };
  target: { x: number; y: number };
  sourceSide: NavGraphNodeSide;
  targetSide: NavGraphNodeSide;
  loopLane: number | null;
}

export interface NavGraphEdgeGeometry {
  path: string;
  labelX: number;
  labelY: number;
}

export function routeNavGraphEdges(
  nodes: readonly NavGraphLayoutNode[],
  edges: readonly NavGraphInspectorEdge[],
): NavGraphEdgeRoute[] {
  const nodesById = new Map(nodes.map((node) => [node.id, node]));
  const base = edges.map((edge) => {
    const source = nodesById.get(edge.from);
    const target = nodesById.get(edge.to);
    if (!source || !target) return null;
    const sides = determineSides(source, target);
    return { edge, source, target, ...sides };
  });
  const resolved = base.filter((value): value is NonNullable<typeof value> => value !== null);
  const sourceGroups = groupOffsets(resolved, "source");
  const targetGroups = groupOffsets(resolved, "target");
  const loopLanes = selfLoopLanes(resolved);

  return resolved.map((entry) => {
    const loopLane = loopLanes.get(entry.edge.id) ?? null;
    if (loopLane !== null) {
      return {
        id: entry.edge.id,
        sourceSide: "right" as const,
        targetSide: "right" as const,
        source: anchor(entry.source, "right", -16 - loopLane * 5),
        target: anchor(entry.target, "right", 16 + loopLane * 5),
        loopLane,
      };
    }
    return {
      id: entry.edge.id,
      sourceSide: entry.sourceSide,
      targetSide: entry.targetSide,
      source: anchor(
        entry.source,
        entry.sourceSide,
        sourceGroups.get(entry.edge.id) ?? 0,
      ),
      target: anchor(
        entry.target,
        entry.targetSide,
        targetGroups.get(entry.edge.id) ?? 0,
      ),
      loopLane,
    };
  });
}

export function navGraphEdgePath(route: NavGraphEdgeRoute): string {
  return navGraphEdgeGeometry(route).path;
}

export function navGraphEdgeGeometry(
  route: NavGraphEdgeRoute,
): NavGraphEdgeGeometry {
  const dx = route.target.x - route.source.x;
  const dy = route.target.y - route.source.y;
  const bend =
    route.loopLane === null
      ? Math.max(48, Math.min(140, Math.hypot(dx, dy) * 0.35))
      : 58 + route.loopLane * 24;
  const sourceControl = control(route.source, route.sourceSide, bend);
  const targetControl = control(route.target, route.targetSide, bend);
  return {
    path: `M ${route.source.x} ${route.source.y} C ${sourceControl.x} ${sourceControl.y}, ${targetControl.x} ${targetControl.y}, ${route.target.x} ${route.target.y}`,
    labelX: cubicMidpoint(
      route.source.x,
      sourceControl.x,
      targetControl.x,
      route.target.x,
    ),
    labelY: cubicMidpoint(
      route.source.y,
      sourceControl.y,
      targetControl.y,
      route.target.y,
    ),
  };
}

function determineSides(source: NavGraphLayoutNode, target: NavGraphLayoutNode) {
  if (source.id === target.id) {
    return { sourceSide: "right", targetSide: "right" } as const;
  }
  const sourceCenter = center(source);
  const targetCenter = center(target);
  const dx = targetCenter.x - sourceCenter.x;
  const dy = targetCenter.y - sourceCenter.y;
  if (Math.abs(dx) >= Math.abs(dy)) {
    return dx >= 0
      ? ({ sourceSide: "right", targetSide: "left" } as const)
      : ({ sourceSide: "left", targetSide: "right" } as const);
  }
  return dy >= 0
    ? ({ sourceSide: "bottom", targetSide: "top" } as const)
    : ({ sourceSide: "top", targetSide: "bottom" } as const);
}

function selfLoopLanes(
  entries: ReadonlyArray<{
    edge: NavGraphInspectorEdge;
    source: NavGraphLayoutNode;
    target: NavGraphLayoutNode;
  }>,
) {
  const groups = new Map<string, typeof entries>();
  for (const entry of entries) {
    if (entry.source.id !== entry.target.id) continue;
    groups.set(entry.source.id, [...(groups.get(entry.source.id) ?? []), entry]);
  }
  const lanes = new Map<string, number>();
  for (const group of groups.values()) {
    [...group]
      .sort((left, right) => left.edge.id.localeCompare(right.edge.id))
      .forEach((entry, index) => lanes.set(entry.edge.id, index));
  }
  return lanes;
}

function groupOffsets(
  entries: ReadonlyArray<{
    edge: NavGraphInspectorEdge;
    source: NavGraphLayoutNode;
    target: NavGraphLayoutNode;
    sourceSide: NavGraphNodeSide;
    targetSide: NavGraphNodeSide;
  }>,
  perspective: "source" | "target",
) {
  const groups = new Map<string, typeof entries>();
  for (const entry of entries) {
    const node = perspective === "source" ? entry.source : entry.target;
    const side = perspective === "source" ? entry.sourceSide : entry.targetSide;
    const key = `${node.id}:${side}`;
    groups.set(key, [...(groups.get(key) ?? []), entry]);
  }
  const offsets = new Map<string, number>();
  for (const group of groups.values()) {
    const sorted = [...group].sort((left, right) =>
      left.edge.id.localeCompare(right.edge.id),
    );
    sorted.forEach((entry, index) => {
      const span = 20;
      const offset =
        sorted.length === 1
          ? 0
          : -span + (span * 2 * index) / (sorted.length - 1);
      offsets.set(entry.edge.id, offset);
    });
  }
  return offsets;
}

function center(node: NavGraphLayoutNode) {
  return {
    x: node.x + NAVGRAPH_NODE_WIDTH / 2,
    y: node.y + NAVGRAPH_NODE_HEIGHT / 2,
  };
}

function anchor(
  node: NavGraphLayoutNode,
  side: NavGraphNodeSide,
  offset: number,
) {
  const nodeCenter = center(node);
  if (side === "left") return { x: node.x, y: nodeCenter.y + offset };
  if (side === "right") {
    return { x: node.x + NAVGRAPH_NODE_WIDTH, y: nodeCenter.y + offset };
  }
  if (side === "top") return { x: nodeCenter.x + offset, y: node.y };
  return {
    x: nodeCenter.x + offset,
    y: node.y + NAVGRAPH_NODE_HEIGHT,
  };
}

function control(
  point: { x: number; y: number },
  side: NavGraphNodeSide,
  distance: number,
) {
  if (side === "left") return { x: point.x - distance, y: point.y };
  if (side === "right") return { x: point.x + distance, y: point.y };
  if (side === "top") return { x: point.x, y: point.y - distance };
  return { x: point.x, y: point.y + distance };
}

function cubicMidpoint(start: number, first: number, second: number, end: number) {
  return (start + 3 * first + 3 * second + end) / 8;
}
