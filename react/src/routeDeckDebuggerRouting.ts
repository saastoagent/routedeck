import type { RouteDeckManifestEdge } from './types'

export type DebuggerSide = 'top' | 'right' | 'bottom' | 'left'

export interface DebuggerLayoutNode {
  id: string
  x: number
  y: number
  width?: number
  height?: number
}

export interface DebuggerIndexedEdge extends RouteDeckManifestEdge {
  route_id: string
}

export interface DebuggerEdgeRoute {
  routeId: string
  sourceSide: DebuggerSide
  targetSide: DebuggerSide
  sourcePoint: { x: number; y: number }
  targetPoint: { x: number; y: number }
  sourceOffset: number
  targetOffset: number
  sourceGroupCount: number
  targetGroupCount: number
  pairOffset: number
}

interface EdgeMeta {
  edge: DebuggerIndexedEdge
  source: Required<DebuggerLayoutNode>
  target: Required<DebuggerLayoutNode>
  sourceSide: DebuggerSide
  targetSide: DebuggerSide
}

const DEFAULT_NODE_WIDTH = 178
const DEFAULT_NODE_HEIGHT = 82
const HORIZONTAL_LANE_SPAN = DEFAULT_NODE_HEIGHT * 0.28
const VERTICAL_LANE_SPAN = DEFAULT_NODE_WIDTH * 0.24
const BIDIRECTIONAL_PAIR_OFFSET = 10
const DUPLICATE_DIRECTION_OFFSET = 4

export function assignDebuggerEdgeRoutes(
  nodes: DebuggerLayoutNode[],
  edges: DebuggerIndexedEdge[],
): Map<string, DebuggerEdgeRoute> {
  const nodesById = new Map(
    nodes.map((node) => [
      node.id,
      {
        ...node,
        width: node.width ?? DEFAULT_NODE_WIDTH,
        height: node.height ?? DEFAULT_NODE_HEIGHT,
      },
    ]),
  )

  const edgeMeta = edges
    .map((edge) => {
      const source = nodesById.get(edge.from)
      const target = nodesById.get(edge.to)
      if (!source || !target) return null
      const { sourceSide, targetSide } = determineEdgeSides(source, target)
      return {
        edge,
        source,
        target,
        sourceSide,
        targetSide,
      } satisfies EdgeMeta
    })
    .filter((value): value is EdgeMeta => Boolean(value))

  const pairOffsets = buildPairOffsets(edgeMeta)
  const sourceOffsets = buildGroupOffsets(edgeMeta, 'source')
  const targetOffsets = buildGroupOffsets(edgeMeta, 'target')

  return new Map(
    edgeMeta.map((meta) => {
      const pairOffset = pairOffsets.get(meta.edge.route_id) || 0
      const sourceOffset = clamp(
        (sourceOffsets.get(meta.edge.route_id) || 0) + pairOffset,
        -laneSpan(meta.sourceSide),
        laneSpan(meta.sourceSide),
      )
      const targetOffset = clamp(
        (targetOffsets.get(meta.edge.route_id) || 0) + pairOffset,
        -laneSpan(meta.targetSide),
        laneSpan(meta.targetSide),
      )
      return [
        meta.edge.route_id,
        {
          routeId: meta.edge.route_id,
          sourceSide: meta.sourceSide,
          targetSide: meta.targetSide,
          sourcePoint: anchorPoint(meta.source, meta.sourceSide, sourceOffset),
          targetPoint: anchorPoint(meta.target, meta.targetSide, targetOffset),
          sourceOffset,
          targetOffset,
          sourceGroupCount: groupSize(edgeMeta, 'source', meta),
          targetGroupCount: groupSize(edgeMeta, 'target', meta),
          pairOffset,
        } satisfies DebuggerEdgeRoute,
      ] as const
    }),
  )
}

export function determineEdgeSides(
  source: DebuggerLayoutNode,
  target: DebuggerLayoutNode,
): { sourceSide: DebuggerSide; targetSide: DebuggerSide } {
  const sourceCenter = centerPoint(source)
  const targetCenter = centerPoint(target)
  const dx = targetCenter.x - sourceCenter.x
  const dy = targetCenter.y - sourceCenter.y

  if (Math.abs(dx) >= Math.abs(dy)) {
    return dx >= 0
      ? { sourceSide: 'right', targetSide: 'left' }
      : { sourceSide: 'left', targetSide: 'right' }
  }

  return dy >= 0
    ? { sourceSide: 'bottom', targetSide: 'top' }
    : { sourceSide: 'top', targetSide: 'bottom' }
}

export function anchorPoint(
  node: DebuggerLayoutNode,
  side: DebuggerSide,
  offset: number,
): { x: number; y: number } {
  const width = node.width ?? DEFAULT_NODE_WIDTH
  const height = node.height ?? DEFAULT_NODE_HEIGHT
  const centerX = node.x + width / 2
  const centerY = node.y + height / 2

  if (side === 'left') return { x: node.x, y: centerY + offset }
  if (side === 'right') return { x: node.x + width, y: centerY + offset }
  if (side === 'top') return { x: centerX + offset, y: node.y }
  return { x: centerX + offset, y: node.y + height }
}

function buildPairOffsets(edgeMeta: EdgeMeta[]) {
  const pairGroups = new Map<string, EdgeMeta[]>()
  for (const meta of edgeMeta) {
    const key = pairKey(meta.edge)
    const current = pairGroups.get(key) || []
    current.push(meta)
    pairGroups.set(key, current)
  }

  const offsets = new Map<string, number>()
  for (const entries of pairGroups.values()) {
    const directions = new Map<string, EdgeMeta[]>()
    for (const meta of entries) {
      const current = directions.get(directionKey(meta.edge)) || []
      current.push(meta)
      directions.set(directionKey(meta.edge), current)
    }

    if (directions.size < 2) {
      for (const meta of entries) offsets.set(meta.edge.route_id, 0)
      continue
    }

    Array.from(directions.entries())
      .sort(([left], [right]) => left.localeCompare(right))
      .forEach(([_, metas], directionIndex, directionGroups) => {
        const polarity = directionGroups.length === 1 ? 0 : directionIndex === 0 ? -1 : 1
        stableMetaSort(metas, 'pair')
        metas.forEach((meta, index) => {
          const duplicateOffset =
            metas.length > 1
              ? centeredOffset(index, metas.length, DUPLICATE_DIRECTION_OFFSET)
              : 0
          offsets.set(meta.edge.route_id, polarity * BIDIRECTIONAL_PAIR_OFFSET + duplicateOffset)
        })
      })
  }

  return offsets
}

function buildGroupOffsets(edgeMeta: EdgeMeta[], perspective: 'source' | 'target') {
  const grouped = new Map<string, EdgeMeta[]>()
  for (const meta of edgeMeta) {
    const side = perspective === 'source' ? meta.sourceSide : meta.targetSide
    const nodeId = perspective === 'source' ? meta.edge.from : meta.edge.to
    const key = `${nodeId}:${side}`
    const current = grouped.get(key) || []
    current.push(meta)
    grouped.set(key, current)
  }

  const offsets = new Map<string, number>()
  for (const metas of grouped.values()) {
    stableMetaSort(metas, perspective)
    const span = laneSpan(perspective === 'source' ? metas[0]!.sourceSide : metas[0]!.targetSide)
    metas.forEach((meta, index) => {
      offsets.set(meta.edge.route_id, centeredOffset(index, metas.length, span))
    })
  }

  return offsets
}

function groupSize(edgeMeta: EdgeMeta[], perspective: 'source' | 'target', meta: EdgeMeta) {
  const nodeId = perspective === 'source' ? meta.edge.from : meta.edge.to
  const side = perspective === 'source' ? meta.sourceSide : meta.targetSide
  return edgeMeta.filter((entry) => {
    const entryNodeId = perspective === 'source' ? entry.edge.from : entry.edge.to
    const entrySide = perspective === 'source' ? entry.sourceSide : entry.targetSide
    return entryNodeId === nodeId && entrySide === side
  }).length
}

function stableMetaSort(edgeMeta: EdgeMeta[], perspective: 'source' | 'target' | 'pair') {
  edgeMeta.sort((left, right) => compareMeta(left, right, perspective))
}

function compareMeta(left: EdgeMeta, right: EdgeMeta, perspective: 'source' | 'target' | 'pair') {
  const leftNode =
    perspective === 'source'
      ? left.target
      : perspective === 'target'
        ? left.source
        : left.target
  const rightNode =
    perspective === 'source'
      ? right.target
      : perspective === 'target'
        ? right.source
        : right.target
  const laneSide =
    perspective === 'source'
      ? left.sourceSide
      : perspective === 'target'
        ? left.targetSide
        : left.sourceSide

  const [leftPrimary, leftSecondary] = sortCoordinates(leftNode, laneSide)
  const [rightPrimary, rightSecondary] = sortCoordinates(rightNode, laneSide)
  if (leftPrimary !== rightPrimary) return leftPrimary - rightPrimary
  if (leftSecondary !== rightSecondary) return leftSecondary - rightSecondary

  if (left.edge.to !== right.edge.to) return left.edge.to.localeCompare(right.edge.to)
  if (left.edge.from !== right.edge.from) return left.edge.from.localeCompare(right.edge.from)

  const leftLabel = edgeDescriptor(left.edge)
  const rightLabel = edgeDescriptor(right.edge)
  if (leftLabel !== rightLabel) return leftLabel.localeCompare(rightLabel)

  return left.edge.route_id.localeCompare(right.edge.route_id)
}

function sortCoordinates(node: DebuggerLayoutNode, side: DebuggerSide) {
  const center = centerPoint(node)
  return side === 'left' || side === 'right'
    ? [center.y, center.x]
    : [center.x, center.y]
}

function pairKey(edge: RouteDeckManifestEdge) {
  return [edge.from, edge.to].sort().join('::')
}

function directionKey(edge: RouteDeckManifestEdge) {
  return `${edge.from}->${edge.to}`
}

function edgeDescriptor(edge: RouteDeckManifestEdge) {
  return edge.action_id || edge.condition || edge.type || 'edge'
}

function centerPoint(node: DebuggerLayoutNode) {
  const width = node.width ?? DEFAULT_NODE_WIDTH
  const height = node.height ?? DEFAULT_NODE_HEIGHT
  return {
    x: node.x + width / 2,
    y: node.y + height / 2,
  }
}

function centeredOffset(index: number, count: number, maxAbs: number) {
  if (count <= 1) return 0
  const step = (maxAbs * 2) / (count - 1)
  return -maxAbs + step * index
}

function laneSpan(side: DebuggerSide) {
  return side === 'left' || side === 'right' ? HORIZONTAL_LANE_SPAN : VERTICAL_LANE_SPAN
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value))
}
