import type { RouteDeckManifestEdge, RouteDeckManifestNode } from './types'

export interface DebuggerRadialTopology {
  positions: Map<string, { x: number; y: number }>
  laneOrder: string[]
  depthById: Map<string, number>
  rootId: string | null
}

const FIRST_RING_RADIUS = 268
const RING_GAP = 172
const NODE_FAN_STEP = 0.24
const MIN_SECTOR_SPAN = 0.38
const MAX_SECTOR_UTILIZATION = 0.78
const DETACHED_COMPONENT_GAP = 1

export function buildDebuggerRadialTopology(
  nodes: RouteDeckManifestNode[],
  edges: RouteDeckManifestEdge[],
  currentNodeId: string | null,
): DebuggerRadialTopology {
  const laneOrder = Array.from(new Set(nodes.map((node) => node.lane || 'main')))
  const nodesById = new Map(nodes.map((node) => [node.id, node]))
  const rootId = nodesById.has('home') ? 'home' : currentNodeId || nodes[0]?.id || null

  if (!rootId) {
    return {
      positions: new Map(),
      laneOrder,
      depthById: new Map(),
      rootId: null,
    }
  }

  const outgoing = buildNeighborMap(nodes, edges, 'outgoing')
  const incoming = buildNeighborMap(nodes, edges, 'incoming')
  const undirected = buildNeighborMap(nodes, edges, 'undirected')
  const degreeById = buildDegreeMap(nodes, edges)

  const depthById = new Map<string, number>([[rootId, 0]])
  const firstHopById = new Map<string, string>([[rootId, rootId]])
  const parentById = new Map<string, string | null>([[rootId, null]])

  const reachableQueue = [rootId]
  while (reachableQueue.length > 0) {
    const currentId = reachableQueue.shift()
    if (!currentId) continue
    const currentDepth = depthById.get(currentId) || 0
    const children = Array.from(outgoing.get(currentId) || []).sort((leftId, rightId) =>
      compareNodeIds(leftId, rightId, nodesById, laneOrder, degreeById),
    )

    for (const childId of children) {
      if (depthById.has(childId)) continue
      depthById.set(childId, currentDepth + 1)
      firstHopById.set(childId, currentId === rootId ? childId : firstHopById.get(currentId) || childId)
      parentById.set(childId, currentId)
      reachableQueue.push(childId)
    }
  }

  const reachableNodeIds = new Set(depthById.keys())
  const reachableMaxDepth = Math.max(...depthById.values())

  const detachedRoots: string[] = []
  for (const node of nodes.sort((left, right) => compareNodeIds(left.id, right.id, nodesById, laneOrder, degreeById))) {
    if (reachableNodeIds.has(node.id)) continue
    const componentNodeIds = collectWeakComponent(node.id, undirected)
      .filter((nodeId) => !depthById.has(nodeId))
      .sort((leftId, rightId) => compareNodeIds(leftId, rightId, nodesById, laneOrder, degreeById))
    if (componentNodeIds.length === 0) continue

    const componentSet = new Set(componentNodeIds)
    const componentRootId = selectComponentRoot(componentNodeIds, nodesById, laneOrder, degreeById, incoming, outgoing)
    detachedRoots.push(componentRootId)

    const componentQueue = [componentRootId]
    depthById.set(componentRootId, reachableMaxDepth + DETACHED_COMPONENT_GAP)
    firstHopById.set(componentRootId, componentRootId)
    parentById.set(componentRootId, null)

    while (componentQueue.length > 0) {
      const currentId = componentQueue.shift()
      if (!currentId) continue
      const currentDepth = depthById.get(currentId) || reachableMaxDepth + DETACHED_COMPONENT_GAP

      const directedChildren = Array.from(outgoing.get(currentId) || [])
        .filter((childId) => componentSet.has(childId))
        .sort((leftId, rightId) => compareNodeIds(leftId, rightId, nodesById, laneOrder, degreeById))

      for (const childId of directedChildren) {
        if (depthById.has(childId)) continue
        depthById.set(childId, currentDepth + 1)
        firstHopById.set(childId, componentRootId)
        parentById.set(childId, currentId)
        componentQueue.push(childId)
      }

      const weakNeighbors = Array.from(undirected.get(currentId) || [])
        .filter((neighborId) => componentSet.has(neighborId))
        .sort((leftId, rightId) => compareNodeIds(leftId, rightId, nodesById, laneOrder, degreeById))

      for (const neighborId of weakNeighbors) {
        if (depthById.has(neighborId)) continue
        depthById.set(neighborId, currentDepth + 1)
        firstHopById.set(neighborId, componentRootId)
        parentById.set(neighborId, currentId)
        componentQueue.push(neighborId)
      }
    }
  }

  const primarySectorIds = Array.from(
    new Set(
      nodes
        .filter((node) => {
          const depth = depthById.get(node.id)
          return depth !== undefined && depth > 0 && reachableNodeIds.has(node.id)
        })
        .map((node) => firstHopById.get(node.id) || node.id),
    ),
  ).sort((leftId, rightId) => compareNodeIds(leftId, rightId, nodesById, laneOrder, degreeById))

  const detachedSectorIds = detachedRoots.sort((leftId, rightId) =>
    compareNodeIds(leftId, rightId, nodesById, laneOrder, degreeById),
  )
  const sectorIds = [...primarySectorIds, ...detachedSectorIds]

  const positions = new Map<string, { x: number; y: number }>()
  positions.set(rootId, { x: 0, y: 0 })

  if (sectorIds.length === 0) {
    return {
      positions,
      laneOrder,
      depthById,
      rootId,
    }
  }

  const step = sectorIds.length === 1 ? Math.PI * 2 : (Math.PI * 2) / sectorIds.length
  const sectorAngleById = new Map(
    sectorIds.map((sectorId, index) => [sectorId, -Math.PI / 2 + step * index] as const),
  )
  const angleById = new Map<string, number>([[rootId, -Math.PI / 2]])

  const sectorDepthGroups = new Map<string, Map<number, RouteDeckManifestNode[]>>()
  for (const node of nodes) {
    if (node.id === rootId) continue
    const depth = depthById.get(node.id)
    const sectorId = firstHopById.get(node.id)
    if (depth === undefined || !sectorId) continue
    const depthGroups = sectorDepthGroups.get(sectorId) || new Map<number, RouteDeckManifestNode[]>()
    const group = depthGroups.get(depth) || []
    group.push(node)
    depthGroups.set(depth, group)
    sectorDepthGroups.set(sectorId, depthGroups)
  }

  for (const sectorId of sectorIds) {
    const depthGroups = sectorDepthGroups.get(sectorId)
    if (!depthGroups) continue
    const sectorCenter = sectorAngleById.get(sectorId) || 0
    const maxSpan = Math.max(MIN_SECTOR_SPAN, step * MAX_SECTOR_UTILIZATION)

    for (const depth of Array.from(depthGroups.keys()).sort((left, right) => left - right)) {
      const group = (depthGroups.get(depth) || [])
        .slice()
        .sort((left, right) => {
          const leftParentAngle = angleById.get(parentById.get(left.id) || '') ?? sectorCenter
          const rightParentAngle = angleById.get(parentById.get(right.id) || '') ?? sectorCenter
          if (leftParentAngle !== rightParentAngle) return leftParentAngle - rightParentAngle
          const leftLane = laneIndex(left.lane, laneOrder)
          const rightLane = laneIndex(right.lane, laneOrder)
          if (leftLane !== rightLane) return leftLane - rightLane
          const labelOrder = left.label.localeCompare(right.label)
          if (labelOrder !== 0) return labelOrder
          return left.id.localeCompare(right.id)
        })

      const radius = FIRST_RING_RADIUS + (depth - 1) * RING_GAP
      const span =
        group.length <= 1
          ? 0
          : Math.min(maxSpan, NODE_FAN_STEP * (group.length - 1))

      group.forEach((node, index) => {
        const angle =
          span === 0
            ? sectorCenter
            : sectorCenter - span / 2 + (span * index) / Math.max(1, group.length - 1)
        positions.set(node.id, {
          x: Math.cos(angle) * radius,
          y: Math.sin(angle) * radius,
        })
        angleById.set(node.id, angle)
      })
    }
  }

  return {
    positions,
    laneOrder,
    depthById,
    rootId,
  }
}

function buildNeighborMap(
  nodes: RouteDeckManifestNode[],
  edges: RouteDeckManifestEdge[],
  mode: 'incoming' | 'outgoing' | 'undirected',
) {
  const map = new Map<string, Set<string>>(nodes.map((node) => [node.id, new Set<string>()]))
  for (const edge of edges) {
    if (mode === 'incoming') {
      map.get(edge.to)?.add(edge.from)
      continue
    }
    map.get(edge.from)?.add(edge.to)
    if (mode === 'undirected') map.get(edge.to)?.add(edge.from)
  }
  return map
}

function buildDegreeMap(nodes: RouteDeckManifestNode[], edges: RouteDeckManifestEdge[]) {
  const degree = new Map(nodes.map((node) => [node.id, 0]))
  for (const edge of edges) {
    degree.set(edge.from, (degree.get(edge.from) || 0) + 1)
    degree.set(edge.to, (degree.get(edge.to) || 0) + 1)
  }
  return degree
}

function collectWeakComponent(rootId: string, neighbors: Map<string, Set<string>>) {
  const seen = new Set<string>()
  const queue = [rootId]
  while (queue.length > 0) {
    const currentId = queue.shift()
    if (!currentId || seen.has(currentId)) continue
    seen.add(currentId)
    for (const neighborId of neighbors.get(currentId) || []) queue.push(neighborId)
  }
  return Array.from(seen)
}

function selectComponentRoot(
  componentNodeIds: string[],
  nodesById: Map<string, RouteDeckManifestNode>,
  laneOrder: string[],
  degreeById: Map<string, number>,
  incoming: Map<string, Set<string>>,
  outgoing: Map<string, Set<string>>,
) {
  return componentNodeIds.slice().sort((leftId, rightId) => {
    const leftIncoming = (incoming.get(leftId) || new Set()).size
    const rightIncoming = (incoming.get(rightId) || new Set()).size
    if (leftIncoming !== rightIncoming) return leftIncoming - rightIncoming

    const leftOutgoing = (outgoing.get(leftId) || new Set()).size
    const rightOutgoing = (outgoing.get(rightId) || new Set()).size
    if (leftOutgoing !== rightOutgoing) return rightOutgoing - leftOutgoing

    return compareNodeIds(leftId, rightId, nodesById, laneOrder, degreeById)
  })[0]!
}

function compareNodeIds(
  leftId: string,
  rightId: string,
  nodesById: Map<string, RouteDeckManifestNode>,
  laneOrder: string[],
  degreeById: Map<string, number>,
) {
  const left = nodesById.get(leftId)
  const right = nodesById.get(rightId)
  if (!left || !right) return leftId.localeCompare(rightId)

  const leftLane = laneIndex(left.lane, laneOrder)
  const rightLane = laneIndex(right.lane, laneOrder)
  if (leftLane !== rightLane) return leftLane - rightLane

  const rightDegree = degreeById.get(right.id) || 0
  const leftDegree = degreeById.get(left.id) || 0
  if (leftDegree !== rightDegree) return rightDegree - leftDegree

  const labelOrder = left.label.localeCompare(right.label)
  if (labelOrder !== 0) return labelOrder
  return left.id.localeCompare(right.id)
}

function laneIndex(lane: string | null | undefined, laneOrder: string[]) {
  const normalizedLane = lane || 'main'
  const index = laneOrder.indexOf(normalizedLane)
  return index >= 0 ? index : laneOrder.length
}
