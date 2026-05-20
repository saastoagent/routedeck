import { useMemo, useState } from 'react'
import {
  Background,
  BaseEdge,
  getBezierPath,
  Handle,
  Position,
  ReactFlow,
  type Edge,
  type EdgeProps,
  type Node,
  type NodeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import type {
  RouteDeckActionCard,
  RouteDeckManifest,
  RouteDeckManifestAction,
  RouteDeckManifestEdge,
  RouteDeckManifestNode,
  RouteDeckRuntimeSnapshot,
} from './types'
import {
  assignDebuggerEdgeRoutes,
  type DebuggerEdgeRoute,
  type DebuggerIndexedEdge,
  type DebuggerSide,
} from './routeDeckDebuggerRouting'

export interface RouteDeckDebuggerProps {
  graphManifest?: RouteDeckManifest | null
  snapshot?: RouteDeckRuntimeSnapshot | null
  selectedNodeId?: string | null
  onSelectedNodeChange: (nodeId: string | null) => void
  onActionSelect?: (action: RouteDeckActionCard) => void
  runId?: string | null
  sessionId?: string | null
  className?: string
  themeMode?: 'light' | 'dark'
  canvasClassName?: string
}

type GraphTone = 'previous' | 'current' | 'next' | 'idle'
type GraphMode = 'focus' | 'map'

interface RouteNodeData extends Record<string, unknown> {
  label: string
  id: string
  lane: string
  tone: GraphTone
  themeMode: 'light' | 'dark'
}

type RouteDeckFlowNode = Node<RouteNodeData>
type RouteDeckFlowEdge = Edge<{
  route: DebuggerEdgeRoute
  quiet?: boolean
}>

const NODE_WIDTH = 178
const NODE_HEIGHT = 82
const REGION_COLORS = ['#2e5fa7', '#95591f', '#2f7f68', '#7e8793', '#bf7d34', '#4e86b7', '#78624b', '#a45a43']
const HIDDEN_HANDLE_CLASS = '!h-0 !w-0 !min-h-0 !min-w-0 !border-0 !bg-transparent !opacity-0'

function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(' ')
}

function edgeLabel(edge: RouteDeckManifestEdge) {
  return edge.action_id || edge.condition || edge.type
}

function shortText(value?: string | null, max = 22) {
  if (!value) return ''
  return value.length > max ? `${value.slice(0, max - 1)}...` : value
}

function toneLabel(tone: GraphTone) {
  if (tone === 'current') return 'You are here'
  if (tone === 'previous') return 'From'
  if (tone === 'next') return 'Next'
  return 'Node'
}

function toneClasses(tone: GraphTone, selected: boolean, themeMode: 'light' | 'dark') {
  if (themeMode === 'dark') {
    if (tone === 'current') {
      return selected
        ? 'border-[#d7e5ff] bg-[#2e5fa7] text-[#f7faff] shadow-[0_20px_36px_-24px_rgba(41,94,168,0.85)]'
        : 'border-[#8eaedf] bg-[#2e5fa7] text-[#f7faff]'
    }
    if (tone === 'previous') {
      return selected
        ? 'border-[#8f97a2] bg-[#2a2d31] text-[#f1f3f6]'
        : 'border-[#616872] bg-[#1b1d21] text-[#eceff3]'
    }
    if (tone === 'next') {
      return selected
        ? 'border-[#e1b07a] bg-[#7a4a19] text-[#fff3e5]'
        : 'border-[#ad7645] bg-[#5d3714] text-[#fff1e4]'
    }
    return selected
      ? 'border-[#8f97a2] bg-[#2a2d31] text-[#f1f3f6]'
      : 'border-[#535961] bg-[#17191c] text-[#e8eaee]'
  }

  if (tone === 'current') {
    return selected
      ? 'border-[#c5d8f6] bg-[#2e5fa7] text-[#f8fbff] shadow-[0_18px_36px_-24px_rgba(46,95,167,0.55)]'
      : 'border-[#9eb8df] bg-[#2e5fa7] text-[#f8fbff]'
  }
  if (tone === 'previous') {
    return selected
      ? 'border-[#8f8a81] bg-[#4f4a43] text-[#fbfaf7]'
      : 'border-[#726d67] bg-[#3c3833] text-[#f6f3ee]'
  }
  if (tone === 'next') {
    return selected
      ? 'border-[#e1bf98] bg-[#9b5e26] text-[#fff7ef]'
      : 'border-[#c48d57] bg-[#7b491c] text-[#fff4e8]'
  }
  return selected
    ? 'border-[#918b83] bg-[#4f4a43] text-[#fbfaf7]'
    : 'border-[#76716a] bg-[#34302c] text-[#f5f2ec]'
}

function RouteDeckNode({ data, selected }: NodeProps<RouteDeckFlowNode>) {
  const isDark = data.themeMode === 'dark'
  return (
    <div
      className={cx(
        'h-[82px] w-[178px] rounded-xl border px-3 py-2 shadow-md transition',
        data.tone === 'current' && 'border-2',
        toneClasses(data.tone, selected, data.themeMode),
      )}
    >
      <Handle type="target" position={Position.Top} className={HIDDEN_HANDLE_CLASS} />
      <div className="flex min-w-0 items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold">{data.label}</div>
          <div className="mt-1 truncate font-mono text-[10px] opacity-70">{data.id}</div>
        </div>
        <span
          className={cx(
            'shrink-0 rounded-[0.55rem] border px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide',
            data.tone === 'current'
              ? isDark
                ? 'border-white/35 bg-white text-[#2e5fa7]'
                : 'border-white/45 bg-white text-[#2e5fa7]'
              : isDark
                ? 'border-white/15 bg-black/20 opacity-80'
                : 'border-black/10 bg-white/15 opacity-85',
          )}
        >
          {toneLabel(data.tone)}
        </span>
      </div>
      <div className="mt-2 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide opacity-70">
        <span
          className={cx(
            'h-1.5 w-1.5 rounded-full',
            data.tone === 'current'
              ? 'bg-white'
              : data.tone === 'next'
                ? 'bg-[#e8bf8f]'
                : isDark
                  ? 'bg-[#c3c7cf]'
                  : 'bg-[#efe9df]',
          )}
        />
        {shortText(data.lane, 12)}
      </div>
      <Handle type="source" position={Position.Bottom} className={HIDDEN_HANDLE_CLASS} />
    </div>
  )
}

const nodeTypes = {
  routeDeck: RouteDeckNode,
}
const edgeTypes = {
  routeDeck: RouteDeckEdge,
}

function positionForSide(side: DebuggerSide) {
  if (side === 'left') return Position.Left
  if (side === 'right') return Position.Right
  if (side === 'top') return Position.Top
  return Position.Bottom
}

function makeRouteEdgeId(edge: RouteDeckManifestEdge, index: number) {
  return `${edge.from}->${edge.to}:${edge.action_id || edge.condition || edge.type || 'edge'}:${index}`
}

function RouteDeckEdge({
  id,
  data,
  label,
  labelStyle,
  labelBgStyle,
  style,
}: EdgeProps<RouteDeckFlowEdge>) {
  if (!data?.route) return null
  const route = data.route
  const [path, labelX, labelY] = getBezierPath({
    sourceX: route.sourcePoint.x,
    sourceY: route.sourcePoint.y,
    sourcePosition: positionForSide(route.sourceSide),
    targetX: route.targetPoint.x,
    targetY: route.targetPoint.y,
    targetPosition: positionForSide(route.targetSide),
    curvature: data.quiet ? 0.18 : 0.24,
  })

  return (
    <BaseEdge
      id={id}
      path={path}
      style={style}
      label={label}
      labelX={labelX}
      labelY={labelY}
      labelStyle={labelStyle}
      labelBgStyle={labelBgStyle}
    />
  )
}

function routeNode(
  node: RouteDeckManifestNode,
  position: { x: number; y: number },
  tone: GraphTone,
  themeMode: 'light' | 'dark',
): RouteDeckFlowNode {
  return {
    id: node.id,
    type: 'routeDeck',
    position,
    data: {
      label: node.label,
      id: node.id,
      lane: node.lane,
      tone,
      themeMode,
    },
    draggable: false,
    style: { width: NODE_WIDTH, height: NODE_HEIGHT },
  }
}

function colorForLane(lane: string | null | undefined, laneOrder: string[] = []) {
  const normalizedLane = lane || 'main'
  const laneIndex = Math.max(0, laneOrder.indexOf(normalizedLane))
  return REGION_COLORS[laneIndex % REGION_COLORS.length]
}

function flowEdge(
  edge: DebuggerIndexedEdge,
  route: DebuggerEdgeRoute,
  currentNodeId: string | null,
  themeMode: 'light' | 'dark',
  options: { showLabel?: boolean; stroke?: string; quiet?: boolean } = {},
): RouteDeckFlowEdge {
  const active = edge.from === currentNodeId || edge.to === currentNodeId
  const showLabel = options.showLabel ?? true
  const stroke = options.stroke || (active ? (themeMode === 'dark' ? '#8eb6ff' : '#2e5fa7') : themeMode === 'dark' ? '#5b616b' : '#908b83')
  const flowEdgeConfig: RouteDeckFlowEdge = {
    id: edge.route_id,
    source: edge.from,
    target: edge.to,
    label: showLabel ? shortText(edgeLabel(edge), 18) : undefined,
    type: 'routeDeck',
    animated: false,
    data: {
      route,
      quiet: options.quiet,
    },
    style: {
      stroke,
      strokeWidth: active ? 2.6 : options.quiet ? 1.05 : 1.35,
      opacity: active ? 0.96 : options.quiet ? 0.34 : 0.58,
    },
  }
  if (showLabel) {
    flowEdgeConfig.labelStyle = {
      fill: active ? (themeMode === 'dark' ? '#eff5ff' : '#f8fbff') : themeMode === 'dark' ? '#d4d8df' : '#f3ede4',
      fontSize: 10,
      fontWeight: 700,
    }
    flowEdgeConfig.labelBgStyle = {
      fill: active ? '#2e5fa7' : themeMode === 'dark' ? '#202227' : '#585148',
      fillOpacity: 0.92,
    }
  }
  return flowEdgeConfig
}

function buildFullMapFlow(
  nodes: RouteDeckManifestNode[],
  edges: RouteDeckManifestEdge[],
  currentNodeId: string | null,
  snapshot: RouteDeckRuntimeSnapshot | null | undefined,
  themeMode: 'light' | 'dark',
): { nodes: RouteDeckFlowNode[]; edges: RouteDeckFlowEdge[] } {
  const nodesById = new Map(nodes.map((node) => [node.id, node]))
  const topology = buildSitemapTopology(nodes, edges, currentNodeId)
  const reachableNodeIds = new Set(snapshot?.reachable_nodes || [])
  const executedNodeIds = new Set(snapshot?.executed_nodes || [])
  const nextNodeIds = new Set(edges.filter((edge) => edge.from === currentNodeId).map((edge) => edge.to))

  const flowNodes: RouteDeckFlowNode[] = []
  for (const node of nodes) {
    const tone: GraphTone =
      node.id === currentNodeId
        ? 'current'
        : nextNodeIds.has(node.id) || reachableNodeIds.has(node.id)
        ? 'next'
        : executedNodeIds.has(node.id)
        ? 'previous'
        : 'idle'
    flowNodes.push(routeNode(node, topology.positions.get(node.id) || { x: 0, y: 0 }, tone, themeMode))
  }

  const layoutNodes = flowNodes.map((node) => ({
    id: node.id,
    x: node.position.x,
    y: node.position.y,
    width: NODE_WIDTH,
    height: NODE_HEIGHT,
  }))
  const indexedEdges: DebuggerIndexedEdge[] = edges.map((edge, index) => ({
    ...edge,
    route_id: makeRouteEdgeId(edge, index),
  }))
  const routes = assignDebuggerEdgeRoutes(layoutNodes, indexedEdges)

  return {
    nodes: flowNodes,
    edges: indexedEdges.flatMap((edge) => {
      const route = routes.get(edge.route_id)
      if (!route) return []
      const sourceLane = nodesById.get(edge.from)?.lane || null
      return flowEdge(edge, route, currentNodeId, themeMode, {
        showLabel: false,
        stroke: colorForLane(sourceLane, topology.laneOrder),
        quiet: true,
      })
    }),
  }
}

function buildSitemapTopology(
  nodes: RouteDeckManifestNode[],
  edges: RouteDeckManifestEdge[],
  currentNodeId: string | null,
): { positions: Map<string, { x: number; y: number }>; laneOrder: string[] } {
  const nodesById = new Map(nodes.map((node) => [node.id, node]))
  const laneOrder = Array.from(new Set(nodes.map((node) => node.lane || 'main')))
  const rootId = nodesById.has('home') ? 'home' : currentNodeId || nodes[0]?.id || null
  const degree = new Map(nodes.map((node) => [node.id, 0]))
  const neighbors = new Map<string, Set<string>>()
  for (const edge of edges) {
    degree.set(edge.from, (degree.get(edge.from) || 0) + 1)
    degree.set(edge.to, (degree.get(edge.to) || 0) + 1)
    const fromNeighbors = neighbors.get(edge.from) || new Set<string>()
    const toNeighbors = neighbors.get(edge.to) || new Set<string>()
    fromNeighbors.add(edge.to)
    toNeighbors.add(edge.from)
    neighbors.set(edge.from, fromNeighbors)
    neighbors.set(edge.to, toNeighbors)
  }

  const hubIds = nodes
    .filter((node) => node.id !== rootId && (degree.get(node.id) || 0) >= 3)
    .sort((left, right) => (degree.get(right.id) || 0) - (degree.get(left.id) || 0))
    .slice(0, 7)
    .map((node) => node.id)
  const hubSet = new Set(hubIds)
  const positions = new Map<string, { x: number; y: number }>()
  if (rootId) positions.set(rootId, { x: 0, y: 0 })

  const hubRadius = 470
  hubIds.forEach((nodeId, index) => {
    const angle = -Math.PI / 2 + (index / Math.max(1, hubIds.length)) * Math.PI * 2
    positions.set(nodeId, {
      x: Math.cos(angle) * hubRadius,
      y: Math.sin(angle) * hubRadius,
    })
  })

  const ownedNodes = new Map<string, RouteDeckManifestNode[]>()
  const leafNodes = nodes.filter((node) => node.id !== rootId && !hubSet.has(node.id))
  for (const node of leafNodes) {
    const ownerId = nearestHub(node.id, hubIds, neighbors) || rootId || hubIds[0]
    if (!ownerId) continue
    const children = ownedNodes.get(ownerId) || []
    children.push(node)
    ownedNodes.set(ownerId, children)
  }

  for (const [ownerId, children] of ownedNodes) {
    const ownerPosition = positions.get(ownerId) || { x: 0, y: 0 }
    const ownerAngle = Math.atan2(ownerPosition.y, ownerPosition.x || 1)
    const spread = Math.min(Math.PI * 0.9, Math.max(Math.PI / 3, children.length * 0.34))
    const childRadius = ownerId === rootId ? 310 : 300
    children
      .sort((left, right) => left.label.localeCompare(right.label))
      .forEach((node, index) => {
        const step = children.length <= 1 ? 0 : index / (children.length - 1)
        const angle = ownerAngle - spread / 2 + spread * step
        const stagger = index % 2 === 0 ? 0 : 54
        positions.set(node.id, {
          x: ownerPosition.x + Math.cos(angle) * (childRadius + stagger),
          y: ownerPosition.y + Math.sin(angle) * (childRadius + stagger),
        })
      })
  }

  for (const node of nodes) {
    if (positions.has(node.id)) continue
    positions.set(node.id, { x: 0, y: positions.size * 150 })
  }

  return { positions, laneOrder }
}

function nearestHub(
  nodeId: string,
  hubIds: string[],
  neighbors: Map<string, Set<string>>,
): string | null {
  const hubSet = new Set(hubIds)
  const queue: Array<{ nodeId: string; distance: number }> = [{ nodeId, distance: 0 }]
  const seen = new Set<string>()
  while (queue.length > 0) {
    const current = queue.shift()
    if (!current || seen.has(current.nodeId)) continue
    seen.add(current.nodeId)
    if (hubSet.has(current.nodeId)) return current.nodeId
    for (const neighbor of neighbors.get(current.nodeId) || []) {
      queue.push({ nodeId: neighbor, distance: current.distance + 1 })
    }
  }
  return null
}

function buildFocusFlow(
  nodesById: Map<string, RouteDeckManifestNode>,
  edges: RouteDeckManifestEdge[],
  currentNodeId: string | null,
  themeMode: 'light' | 'dark',
): { nodes: RouteDeckFlowNode[]; edges: RouteDeckFlowEdge[] } {
  if (!currentNodeId) return { nodes: [], edges: [] }
  const currentNode = nodesById.get(currentNodeId)
  if (!currentNode) return { nodes: [], edges: [] }

  const incomingEdges = edges.filter((edge) => edge.to === currentNodeId).slice(0, 3)
  const outgoingEdges = edges.filter((edge) => edge.from === currentNodeId).slice(0, 3)
  const incomingNodeIds = Array.from(new Set(incomingEdges.map((edge) => edge.from))).slice(0, 3)
  const outgoingNodeIds = Array.from(new Set(outgoingEdges.map((edge) => edge.to))).slice(0, 3)
  const yFor = (count: number, index: number) => (index - (count - 1) / 2) * 112

  const flowNodes: RouteDeckFlowNode[] = [
    ...incomingNodeIds
      .map((nodeId, index) => {
        const node = nodesById.get(nodeId)
        return node ? routeNode(node, { x: 0, y: yFor(incomingNodeIds.length, index) }, 'previous', themeMode) : null
      })
      .filter((node): node is RouteDeckFlowNode => Boolean(node)),
    routeNode(currentNode, { x: 290, y: 0 }, 'current', themeMode),
    ...outgoingNodeIds
      .map((nodeId, index) => {
        const node = nodesById.get(nodeId)
        return node ? routeNode(node, { x: 580, y: yFor(outgoingNodeIds.length, index) }, 'next', themeMode) : null
      })
      .filter((node): node is RouteDeckFlowNode => Boolean(node)),
  ]
  const layoutNodes = flowNodes.map((node) => ({
    id: node.id,
    x: node.position.x,
    y: node.position.y,
    width: NODE_WIDTH,
    height: NODE_HEIGHT,
  }))
  const visibleEdges = [...incomingEdges, ...outgoingEdges].map((edge, index) => ({
    ...edge,
    route_id: makeRouteEdgeId(edge, index),
  }))
  const routes = assignDebuggerEdgeRoutes(layoutNodes, visibleEdges)

  return {
    nodes: flowNodes,
    edges: visibleEdges.flatMap((edge) => {
      const route = routes.get(edge.route_id)
      if (!route) return []
      return flowEdge(edge, route, currentNodeId, themeMode)
    }),
  }
}

function ActionPill({
  action,
  valid,
  themeMode,
}: {
  action: Pick<RouteDeckManifestAction, 'id' | 'label'>
  valid: boolean
  themeMode: 'light' | 'dark'
}) {
  return (
    <span
      className={cx(
        'inline-flex min-w-0 max-w-full items-center gap-2 rounded-[0.8rem] border px-3 py-1.5',
        valid
          ? themeMode === 'dark'
            ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-50'
            : 'border-emerald-200 bg-emerald-50 text-emerald-950'
          : themeMode === 'dark'
            ? 'border-white/10 bg-white/[0.04] text-slate-300'
            : 'border-[#d9d0c4] bg-[#f4efe6] text-[#5b544b]',
      )}
      title={action.id}
    >
      <span className={cx('h-1.5 w-1.5 shrink-0 rounded-full', valid ? 'bg-emerald-500' : 'bg-slate-400')} />
      <span className="truncate text-xs font-semibold">{action.label}</span>
      <span className="truncate font-mono text-[10px] opacity-65">{action.id}</span>
    </span>
  )
}

export function RouteDeckDebugger({
  graphManifest,
  snapshot,
  selectedNodeId,
  onSelectedNodeChange,
  onActionSelect,
  runId,
  sessionId,
  className = '',
  themeMode = 'light',
  canvasClassName = 'h-[30rem]',
}: RouteDeckDebuggerProps) {
  const isDark = themeMode === 'dark'
  const nodes = graphManifest?.nodes || []
  const edges = graphManifest?.edges || []
  const nodesById = useMemo(() => new Map(nodes.map((node) => [node.id, node])), [nodes])
  const [graphMode, setGraphMode] = useState<GraphMode>('focus')
  const actionById = useMemo(() => new Map((graphManifest?.actions || []).map((action) => [action.id, action])), [graphManifest?.actions])
  const currentNodeId = snapshot?.current_node || selectedNodeId || nodes[0]?.id || null
  const selectedId = selectedNodeId || currentNodeId
  const currentNode = currentNodeId ? nodesById.get(currentNodeId) || null : null
  const selectedNode = selectedId ? nodesById.get(selectedId) || currentNode : currentNode
  const selectedActionIds = selectedNode?.allowed_actions || []
  const validActions = snapshot?.valid_actions || []
  const validActionIds = new Set(validActions.map((action) => action.id))
  const actions = selectedActionIds.map((actionId) => actionById.get(actionId) || { id: actionId, label: actionId }).slice(0, 10)
  const flow = useMemo(
    () =>
      graphMode === 'map'
        ? buildFullMapFlow(nodes, edges, currentNodeId, snapshot, themeMode)
        : buildFocusFlow(nodesById, edges, currentNodeId, themeMode),
    [currentNodeId, edges, graphMode, nodes, nodesById, snapshot, themeMode],
  )

  function exportSnapshot() {
    const payload = {
      manifest: graphManifest,
      snapshot,
      run_id: runId,
      session_id: sessionId,
      exported_at: new Date().toISOString(),
    }
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `route-deck-snapshot-${Date.now()}.json`
    link.click()
    URL.revokeObjectURL(url)
  }

  if (!graphManifest || !currentNode) {
    return (
      <div
        className={cx(
          'rounded-xl border p-3 text-xs',
          isDark ? 'border-white/10 bg-white/[0.03]' : 'border-[#ddd4c7] bg-[#f5f0e7]',
          className,
        )}
      >
        <div className={cx('font-semibold', isDark ? 'text-slate-200' : 'text-[#49433b]')}>RouteDeck map</div>
        <div className={cx('mt-2', isDark ? 'text-slate-400' : 'text-[#736b60]')}>No RouteDeck manifest is available for this runtime.</div>
      </div>
    )
  }

  return (
    <div className={`space-y-4 text-xs ${className}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className={cx('font-semibold', isDark ? 'text-white' : 'text-[#2e2b26]')}>
            {graphMode === 'map' ? 'RouteDeck full map' : 'Focused route graph'}
          </div>
          <div className={cx('mt-1', isDark ? 'text-slate-400' : 'text-[#736b60]')}>
            {graphMode === 'map'
              ? 'Showing the full RouteDeck atlas with all nodes and all routes.'
              : 'Showing where you are and the immediate graph transitions.'}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div
            className={cx(
              'inline-flex rounded-[0.8rem] border p-0.5',
              isDark ? 'border-white/10 bg-white/[0.05]' : 'border-[#ddd4c7] bg-[#faf6ef]',
            )}
          >
            {(['focus', 'map'] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => setGraphMode(mode)}
                className={cx(
                  'rounded-[0.65rem] px-3 py-1 text-xs font-medium transition',
                  graphMode === mode
                    ? isDark
                      ? 'bg-white text-slate-950'
                      : 'bg-[#2e5fa7] text-white'
                    : isDark
                      ? 'text-slate-300 hover:text-white'
                      : 'text-[#736b60] hover:text-[#2e2b26]',
                )}
              >
                {mode === 'focus' ? 'Focus' : 'Full map'}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={exportSnapshot}
            className={cx(
              'rounded-[0.8rem] border px-3 py-1.5 text-xs font-medium transition',
              isDark
                ? 'border-white/10 bg-white/[0.05] text-slate-300 hover:bg-white/[0.09]'
                : 'border-[#ddd4c7] bg-[#faf6ef] text-[#5f574d] hover:bg-[#f1ece3]',
            )}
          >
            Export JSON
          </button>
        </div>
      </div>

      {graphMode === 'map' && (
        <div
          className={cx(
            'rounded-xl border px-3 py-2 text-[11px]',
            isDark
              ? 'border-white/10 bg-white/[0.04] text-slate-300'
              : 'border-[#ddd4c7] bg-[#f5f0e7] text-[#625b51]',
          )}
        >
          Showing all {nodes.length} nodes and {edges.length} routes. Edge labels are kept out of the map to reduce clutter; select a node for details.
        </div>
      )}

      <div
        className={cx(
          canvasClassName,
          'overflow-hidden rounded-[0.95rem] border shadow-inner',
          isDark
            ? 'border-white/10 bg-[#15171a]'
            : 'border-[#d9d0c4] bg-[linear-gradient(180deg,#f8f3ea,#efe7da)]',
        )}
      >
        <ReactFlow
          key={`${graphMode}-${themeMode}`}
          nodes={flow.nodes}
          edges={flow.edges}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          fitView
          fitViewOptions={{ padding: graphMode === 'map' ? 0.26 : 0.34 }}
          minZoom={0.16}
          maxZoom={1.5}
          panOnDrag
          zoomOnScroll
          zoomOnPinch
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable
          onNodeClick={(_, node) => {
            if (!String(node.id).startsWith('group:')) onSelectedNodeChange(node.id)
          }}
        >
          <Background color={isDark ? '#2e3238' : '#d4cabc'} gap={24} />
        </ReactFlow>
      </div>

      <div
        className={cx(
          'space-y-3 rounded-[0.95rem] border p-3',
          isDark
            ? 'border-white/10 bg-white/[0.04]'
            : 'border-[#ddd4c7] bg-[#fbf7f0]',
        )}
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div className={cx('font-semibold', isDark ? 'text-white' : 'text-[#2e2b26]')}>{selectedNode?.label || 'Selected node'}</div>
            <div className={cx('mt-0.5 font-mono text-[11px]', isDark ? 'text-slate-400' : 'text-[#736b60]')}>{selectedNode?.id || 'none'}</div>
          </div>
          <span
            className={cx(
              'rounded-[0.65rem] border px-2 py-1 text-[10px] uppercase',
              isDark ? 'border-white/10 text-slate-300' : 'border-[#ddd4c7] text-[#6a6258]',
            )}
          >
            {selectedNode?.lane || 'node'}
          </span>
        </div>

        <div>
          <div className={cx('mb-2 text-[10px] font-semibold uppercase tracking-[0.14em]', isDark ? 'text-slate-400' : 'text-[#8d8478]')}>Selected node actions</div>
          <div className="flex flex-wrap gap-2">
            {actions.length > 0 ? actions.map((action) => (
              <span key={action.id}>
                <ActionPill action={action} valid={validActionIds.has(action.id) || selectedActionIds.includes(action.id)} themeMode={themeMode} />
              </span>
            )) : (
              <span
                className={cx(
                  'rounded-[0.8rem] border border-dashed px-3 py-1.5',
                  isDark ? 'border-white/10 text-slate-400' : 'border-[#ddd4c7] text-[#8d8478]',
                )}
              >
                No allowed actions
              </span>
            )}
          </div>
        </div>

        {(selectedNode?.expected_input || selectedNode?.recovery_prompt) && (
          <div className="grid gap-2 sm:grid-cols-2">
            {selectedNode?.expected_input && (
              <div
                className={cx(
                  'rounded-xl border px-3 py-2',
                  isDark
                    ? 'border-white/10 bg-black/20 text-slate-300'
                    : 'border-[#ddd4c7] bg-[#f5f0e7] text-[#625b51]',
                )}
              >
                <span className={cx('font-semibold', isDark ? 'text-slate-100' : 'text-[#3b352e]')}>Input:</span> {selectedNode.expected_input}
              </div>
            )}
            {selectedNode?.recovery_prompt && (
              <div
                className={cx(
                  'rounded-xl border px-3 py-2',
                  isDark
                    ? 'border-amber-500/30 bg-amber-500/10 text-amber-100'
                    : 'border-[#e5c39d] bg-[#fff2e2] text-[#8a4f16]',
                )}
              >
                <span className="font-semibold">Recovery:</span> {selectedNode.recovery_prompt}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
