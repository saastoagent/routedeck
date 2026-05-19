import { useMemo, useState } from 'react'
import {
  Background,
  Handle,
  Position,
  ReactFlow,
  type Edge,
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

export interface RouteDeckDebuggerProps {
  graphManifest?: RouteDeckManifest | null
  snapshot?: RouteDeckRuntimeSnapshot | null
  selectedNodeId?: string | null
  onSelectedNodeChange: (nodeId: string | null) => void
  onActionSelect?: (action: RouteDeckActionCard) => void
  runId?: string | null
  sessionId?: string | null
  className?: string
}

type GraphTone = 'previous' | 'current' | 'next' | 'idle'
type GraphMode = 'focus' | 'map'

interface RouteNodeData extends Record<string, unknown> {
  label: string
  id: string
  lane: string
  tone: GraphTone
}

type RouteDeckFlowNode = Node<RouteNodeData>

const NODE_WIDTH = 178
const NODE_HEIGHT = 82
const REGION_COLORS = ['#38bdf8', '#a78bfa', '#34d399', '#fbbf24', '#fb7185', '#22d3ee', '#c084fc', '#f97316']

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

function toneClasses(tone: GraphTone, selected: boolean) {
  if (tone === 'current') {
    return selected
      ? 'border-sky-100 bg-sky-700 text-sky-50 shadow-lg shadow-sky-950/25'
      : 'border-sky-200 bg-sky-800 text-sky-50'
  }
  if (tone === 'previous') {
    return selected
      ? 'border-slate-100 bg-slate-800 text-slate-50'
      : 'border-slate-500 bg-slate-950 text-slate-100'
  }
  if (tone === 'next') {
    return selected
      ? 'border-amber-100 bg-amber-800 text-amber-50'
      : 'border-amber-400 bg-amber-950 text-amber-50'
  }
  return selected
    ? 'border-slate-100 bg-slate-800 text-slate-50'
    : 'border-slate-600 bg-slate-950 text-slate-100'
}

function RouteDeckNode({ data, selected }: NodeProps<RouteDeckFlowNode>) {
  return (
    <div
      className={cx(
        'h-[82px] w-[178px] rounded-xl border px-3 py-2 shadow-md transition',
        data.tone === 'current' && 'border-2',
        toneClasses(data.tone, selected),
      )}
    >
      <Handle type="target" position={Position.Top} className="!h-2 !w-2 !border-slate-900 !bg-slate-200" />
      <div className="flex min-w-0 items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold">{data.label}</div>
          <div className="mt-1 truncate font-mono text-[10px] opacity-70">{data.id}</div>
        </div>
        <span
          className={cx(
            'shrink-0 rounded-full border px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide',
            data.tone === 'current'
              ? 'border-white/40 bg-white text-sky-900'
              : 'border-white/15 bg-black/20 opacity-80',
          )}
        >
          {toneLabel(data.tone)}
        </span>
      </div>
      <div className="mt-2 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide opacity-70">
        <span className={cx('h-1.5 w-1.5 rounded-full', data.tone === 'current' ? 'bg-white' : data.tone === 'next' ? 'bg-amber-300' : 'bg-slate-300')} />
        {shortText(data.lane, 12)}
      </div>
      <Handle type="source" position={Position.Bottom} className="!h-2 !w-2 !border-slate-900 !bg-slate-200" />
    </div>
  )
}

const nodeTypes = {
  routeDeck: RouteDeckNode,
}

function routeNode(
  node: RouteDeckManifestNode,
  position: { x: number; y: number },
  tone: GraphTone,
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
  edge: RouteDeckManifestEdge,
  currentNodeId: string | null,
  options: { showLabel?: boolean; stroke?: string; quiet?: boolean } = {},
): Edge {
  const active = edge.from === currentNodeId || edge.to === currentNodeId
  const showLabel = options.showLabel ?? true
  const stroke = options.stroke || (active ? '#38bdf8' : '#64748b')
  const flowEdgeConfig: Edge = {
    id: `${edge.from}-${edge.to}-${edgeLabel(edge)}`,
    source: edge.from,
    target: edge.to,
    label: showLabel ? shortText(edgeLabel(edge), 18) : undefined,
    type: 'default',
    animated: false,
    style: {
      stroke,
      strokeWidth: active ? 2.6 : options.quiet ? 1.05 : 1.35,
      opacity: active ? 0.96 : options.quiet ? 0.34 : 0.58,
    },
  }
  if (showLabel) {
    flowEdgeConfig.labelStyle = {
      fill: active ? '#e0f2fe' : '#cbd5e1',
      fontSize: 10,
      fontWeight: 700,
    }
    flowEdgeConfig.labelBgStyle = {
      fill: active ? '#075985' : '#0f172a',
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
): { nodes: RouteDeckFlowNode[]; edges: Edge[] } {
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
    flowNodes.push(routeNode(node, topology.positions.get(node.id) || { x: 0, y: 0 }, tone))
  }

  return {
    nodes: flowNodes,
    edges: edges.map((edge) => {
      const sourceLane = nodesById.get(edge.from)?.lane || null
      return flowEdge(edge, currentNodeId, {
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
): { nodes: RouteDeckFlowNode[]; edges: Edge[] } {
  if (!currentNodeId) return { nodes: [], edges: [] }
  const currentNode = nodesById.get(currentNodeId)
  if (!currentNode) return { nodes: [], edges: [] }

  const incomingEdges = edges.filter((edge) => edge.to === currentNodeId).slice(0, 2)
  const outgoingEdges = edges.filter((edge) => edge.from === currentNodeId).slice(0, 3)
  const incomingNodeIds = Array.from(new Set(incomingEdges.map((edge) => edge.from))).slice(0, 2)
  const outgoingNodeIds = Array.from(new Set(outgoingEdges.map((edge) => edge.to))).slice(0, 3)
  const yFor = (count: number, index: number) => (index - (count - 1) / 2) * 104

  const flowNodes: RouteDeckFlowNode[] = [
    ...incomingNodeIds
      .map((nodeId, index) => {
        const node = nodesById.get(nodeId)
        return node ? routeNode(node, { x: 0, y: yFor(incomingNodeIds.length, index) }, 'previous') : null
      })
      .filter((node): node is RouteDeckFlowNode => Boolean(node)),
    routeNode(currentNode, { x: 260, y: 0 }, 'current'),
    ...outgoingNodeIds
      .map((nodeId, index) => {
        const node = nodesById.get(nodeId)
        return node ? routeNode(node, { x: 520, y: yFor(outgoingNodeIds.length, index) }, 'next') : null
      })
      .filter((node): node is RouteDeckFlowNode => Boolean(node)),
  ]
  return {
    nodes: flowNodes,
    edges: [...incomingEdges, ...outgoingEdges].map((edge) => flowEdge(edge, currentNodeId)),
  }
}

function ActionPill({ action, valid }: { action: Pick<RouteDeckManifestAction, 'id' | 'label'>; valid: boolean }) {
  return (
    <span
      className={cx(
        'inline-flex min-w-0 max-w-full items-center gap-2 rounded-full border px-3 py-1.5',
        valid
          ? 'border-emerald-200 bg-emerald-50 text-emerald-950 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-50'
          : 'border-slate-200 bg-slate-50 text-slate-700 dark:border-white/10 dark:bg-white/[0.04] dark:text-slate-300',
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
}: RouteDeckDebuggerProps) {
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
        ? buildFullMapFlow(nodes, edges, currentNodeId, snapshot)
        : buildFocusFlow(nodesById, edges, currentNodeId),
    [currentNodeId, edges, graphMode, nodes, nodesById, snapshot],
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
      <div className={`rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs dark:border-white/10 dark:bg-white/[0.03] ${className}`}>
        <div className="font-semibold text-slate-700 dark:text-slate-200">RouteDeck map</div>
        <div className="mt-2 text-slate-500 dark:text-slate-400">No RouteDeck manifest is available for this runtime.</div>
      </div>
    )
  }

  return (
    <div className={`space-y-4 text-xs ${className}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="font-semibold text-slate-900 dark:text-white">
            {graphMode === 'map' ? 'RouteDeck full map' : 'Focused route graph'}
          </div>
          <div className="mt-1 text-slate-500 dark:text-slate-400">
            {graphMode === 'map'
              ? 'Showing the full RouteDeck atlas with all nodes and all routes.'
              : 'Showing where you are and the immediate graph transitions.'}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="inline-flex rounded-full border border-slate-200 bg-white p-0.5 dark:border-white/10 dark:bg-white/[0.05]">
            {(['focus', 'map'] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => setGraphMode(mode)}
                className={cx(
                  'rounded-full px-3 py-1 text-xs font-medium transition',
                  graphMode === mode
                    ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-950'
                    : 'text-slate-500 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white',
                )}
              >
                {mode === 'focus' ? 'Focus' : 'Full map'}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={exportSnapshot}
            className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:bg-slate-100 dark:border-white/10 dark:bg-white/[0.05] dark:text-slate-300 dark:hover:bg-white/[0.09]"
          >
            Export JSON
          </button>
        </div>
      </div>

      {graphMode === 'map' && (
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-[11px] text-slate-600 dark:border-white/10 dark:bg-white/[0.04] dark:text-slate-300">
          Showing all {nodes.length} nodes and {edges.length} routes. Edge labels are kept out of the map to reduce clutter; select a node for details.
        </div>
      )}

      <div className="h-[30rem] overflow-hidden rounded-2xl border border-slate-200 bg-slate-950 shadow-inner dark:border-white/10">
        <ReactFlow
          key={graphMode}
          nodes={flow.nodes}
          edges={flow.edges}
          nodeTypes={nodeTypes}
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
          <Background color="#334155" gap={24} />
        </ReactFlow>
      </div>

      <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-3 dark:border-white/10 dark:bg-white/[0.04]">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div className="font-semibold text-slate-900 dark:text-white">{selectedNode?.label || 'Selected node'}</div>
            <div className="mt-0.5 font-mono text-[11px] text-slate-500 dark:text-slate-400">{selectedNode?.id || 'none'}</div>
          </div>
          <span className="rounded-full border border-slate-200 px-2 py-1 text-[10px] uppercase text-slate-500 dark:border-white/10 dark:text-slate-300">
            {selectedNode?.lane || 'node'}
          </span>
        </div>

        <div>
          <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Selected node actions</div>
          <div className="flex flex-wrap gap-2">
            {actions.length > 0 ? actions.map((action) => (
              <span key={action.id}>
                <ActionPill action={action} valid={validActionIds.has(action.id) || selectedActionIds.includes(action.id)} />
              </span>
            )) : <span className="rounded-full border border-dashed border-slate-200 px-3 py-1.5 text-slate-400 dark:border-white/10">No allowed actions</span>}
          </div>
        </div>

        {(selectedNode?.expected_input || selectedNode?.recovery_prompt) && (
          <div className="grid gap-2 sm:grid-cols-2">
            {selectedNode?.expected_input && (
              <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-slate-600 dark:border-white/10 dark:bg-black/20 dark:text-slate-300">
                <span className="font-semibold text-slate-800 dark:text-slate-100">Input:</span> {selectedNode.expected_input}
              </div>
            )}
            {selectedNode?.recovery_prompt && (
              <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-100">
                <span className="font-semibold">Recovery:</span> {selectedNode.recovery_prompt}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
