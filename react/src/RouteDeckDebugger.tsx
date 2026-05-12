import { useMemo, useState } from 'react'
import {
  Background,
  Controls,
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
type MapMode = 'focus' | 'full'

interface RouteNodeData extends Record<string, unknown> {
  label: string
  id: string
  lane: string
  tone: GraphTone
}

interface GroupNodeData extends Record<string, unknown> {
  label: string
}

type RouteDeckFlowNode = Node<RouteNodeData>
type RouteDeckGroupNode = Node<GroupNodeData>
type RouteDeckAnyNode = RouteDeckFlowNode | RouteDeckGroupNode

const LANE_ORDER = ['system', 'auth', 'workspace', 'terminal']
const NODE_WIDTH = 190
const NODE_HEIGHT = 76
const COL_GAP = 82
const ROW_GAP = 210

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

function toneClasses(tone: GraphTone, selected: boolean) {
  if (tone === 'current') {
    return selected
      ? 'border-sky-100 bg-sky-800 text-sky-50 shadow-lg shadow-sky-950/25'
      : 'border-sky-300 bg-sky-900 text-sky-50'
  }
  if (tone === 'previous') {
    return selected
      ? 'border-emerald-100 bg-emerald-800 text-emerald-50'
      : 'border-emerald-500 bg-emerald-950 text-emerald-50'
  }
  if (tone === 'next') {
    return selected
      ? 'border-amber-100 bg-amber-800 text-amber-50'
      : 'border-amber-500 bg-amber-950 text-amber-50'
  }
  return selected
    ? 'border-slate-100 bg-slate-800 text-slate-50'
    : 'border-slate-600 bg-slate-950 text-slate-100'
}

function RouteDeckNode({ data, selected }: NodeProps<RouteDeckFlowNode>) {
  return (
    <div
      className={cx(
        'h-[76px] w-[190px] rounded-xl border px-3 py-2 shadow-md transition',
        toneClasses(data.tone, selected),
      )}
    >
      <Handle type="target" position={Position.Top} className="!h-2 !w-2 !border-slate-900 !bg-slate-200" />
      <div className="flex min-w-0 items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold">{data.label}</div>
          <div className="mt-1 truncate font-mono text-[10px] opacity-70">{data.id}</div>
        </div>
        <span className="shrink-0 rounded-full border border-white/15 bg-black/20 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide opacity-80">
          {shortText(data.lane, 8)}
        </span>
      </div>
      <div className="mt-2 text-[10px] font-semibold uppercase tracking-wide opacity-70">{data.tone}</div>
      <Handle type="source" position={Position.Bottom} className="!h-2 !w-2 !border-slate-900 !bg-slate-200" />
    </div>
  )
}

function PhaseGroupNode({ data }: NodeProps<RouteDeckGroupNode>) {
  return (
    <div className="h-full w-full rounded-2xl border border-dashed border-slate-500/45 bg-slate-900/40 px-4 py-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
      {data.label}
    </div>
  )
}

const nodeTypes = {
  routeDeck: RouteDeckNode,
  phaseGroup: PhaseGroupNode,
}

function nodeTone(
  nodeId: string,
  currentNodeId: string | null,
  executedNodes: Set<string>,
  previousNodes: Set<string>,
  nextNodes: Set<string>,
): GraphTone {
  if (nodeId === currentNodeId) return 'current'
  if (previousNodes.has(nodeId) || executedNodes.has(nodeId)) return 'previous'
  if (nextNodes.has(nodeId)) return 'next'
  return 'idle'
}

function orderedLanes(nodes: RouteDeckManifestNode[]) {
  const lanes = new Set(nodes.map((node) => node.lane || 'workspace'))
  return [
    ...LANE_ORDER.filter((lane) => lanes.has(lane)),
    ...Array.from(lanes).filter((lane) => !LANE_ORDER.includes(lane)),
  ]
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

function flowEdge(edge: RouteDeckManifestEdge, currentNodeId: string | null): Edge {
  const active = edge.from === currentNodeId || edge.to === currentNodeId
  return {
    id: `${edge.from}-${edge.to}-${edgeLabel(edge)}`,
    source: edge.from,
    target: edge.to,
    label: shortText(edgeLabel(edge), 22),
    type: 'smoothstep',
    animated: active,
    style: {
      stroke: active ? '#38bdf8' : '#64748b',
      strokeWidth: active ? 2.5 : 1.4,
    },
    labelStyle: {
      fill: active ? '#e0f2fe' : '#cbd5e1',
      fontSize: 10,
      fontWeight: 700,
    },
    labelBgStyle: {
      fill: active ? '#075985' : '#0f172a',
      fillOpacity: 0.92,
    },
  }
}

function buildFocusFlow(
  nodesById: Map<string, RouteDeckManifestNode>,
  edges: RouteDeckManifestEdge[],
  currentNodeId: string | null,
): { nodes: RouteDeckAnyNode[]; edges: Edge[] } {
  if (!currentNodeId) return { nodes: [], edges: [] }
  const currentNode = nodesById.get(currentNodeId)
  if (!currentNode) return { nodes: [], edges: [] }

  const incomingEdges = edges.filter((edge) => edge.to === currentNodeId).slice(0, 4)
  const outgoingEdges = edges.filter((edge) => edge.from === currentNodeId).slice(0, 4)
  const incomingNodeIds = Array.from(new Set(incomingEdges.map((edge) => edge.from))).slice(0, 4)
  const outgoingNodeIds = Array.from(new Set(outgoingEdges.map((edge) => edge.to))).slice(0, 4)
  const yFor = (count: number, index: number) => (index - (count - 1) / 2) * 112

  const flowNodes: RouteDeckAnyNode[] = [
    ...incomingNodeIds
      .map((nodeId, index) => {
        const node = nodesById.get(nodeId)
        return node ? routeNode(node, { x: 0, y: yFor(incomingNodeIds.length, index) }, 'previous') : null
      })
      .filter((node): node is RouteDeckFlowNode => Boolean(node)),
    routeNode(currentNode, { x: 310, y: 0 }, 'current'),
    ...outgoingNodeIds
      .map((nodeId, index) => {
        const node = nodesById.get(nodeId)
        return node ? routeNode(node, { x: 620, y: yFor(outgoingNodeIds.length, index) }, 'next') : null
      })
      .filter((node): node is RouteDeckFlowNode => Boolean(node)),
  ]
  return {
    nodes: flowNodes,
    edges: [...incomingEdges, ...outgoingEdges].map((edge) => flowEdge(edge, currentNodeId)),
  }
}

function buildFullFlow(
  nodes: RouteDeckManifestNode[],
  edges: RouteDeckManifestEdge[],
  currentNodeId: string | null,
  executedNodeIds: string[],
): { nodes: RouteDeckAnyNode[]; edges: Edge[] } {
  const lanes = orderedLanes(nodes)
  const previousNodes = new Set(edges.filter((edge) => edge.to === currentNodeId).map((edge) => edge.from))
  const nextNodes = new Set(edges.filter((edge) => edge.from === currentNodeId).map((edge) => edge.to))
  const executedNodes = new Set(executedNodeIds)
  const flowNodes: RouteDeckAnyNode[] = []
  const groupBounds = new Map<string, { minX: number; maxX: number; minY: number; maxY: number }>()

  for (const [laneIndex, lane] of lanes.entries()) {
    const laneNodes = nodes.filter((node) => (node.lane || 'workspace') === lane)
    laneNodes.forEach((node, index) => {
      const position = {
        x: index * (NODE_WIDTH + COL_GAP),
        y: laneIndex * ROW_GAP,
      }
      const tone = nodeTone(node.id, currentNodeId, executedNodes, previousNodes, nextNodes)
      flowNodes.push(routeNode(node, position, tone))

      if (node.parent) {
        const current = groupBounds.get(node.parent) || {
          minX: position.x,
          maxX: position.x,
          minY: position.y,
          maxY: position.y,
        }
        groupBounds.set(node.parent, {
          minX: Math.min(current.minX, position.x),
          maxX: Math.max(current.maxX, position.x),
          minY: Math.min(current.minY, position.y),
          maxY: Math.max(current.maxY, position.y),
        })
      }
    })
  }

  const groupNodes: RouteDeckGroupNode[] = Array.from(groupBounds.entries()).map(([groupId, bounds]) => ({
    id: `group:${groupId}`,
    type: 'phaseGroup',
    position: { x: bounds.minX - 28, y: bounds.minY - 54 },
    data: { label: `${groupId} phase` },
    selectable: false,
    draggable: false,
    zIndex: -1,
    style: {
      width: bounds.maxX - bounds.minX + NODE_WIDTH + 56,
      height: bounds.maxY - bounds.minY + NODE_HEIGHT + 88,
    },
  }))

  return {
    nodes: [...groupNodes, ...flowNodes],
    edges: edges.map((edge) => flowEdge(edge, currentNodeId)),
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
  const [mode, setMode] = useState<MapMode>('focus')
  const nodes = graphManifest?.nodes || []
  const edges = graphManifest?.edges || []
  const nodesById = useMemo(() => new Map(nodes.map((node) => [node.id, node])), [nodes])
  const actionById = useMemo(() => new Map((graphManifest?.actions || []).map((action) => [action.id, action])), [graphManifest?.actions])
  const currentNodeId = snapshot?.current_node || selectedNodeId || nodes[0]?.id || null
  const selectedId = selectedNodeId || currentNodeId
  const currentNode = currentNodeId ? nodesById.get(currentNodeId) || null : null
  const selectedNode = selectedId ? nodesById.get(selectedId) || currentNode : currentNode
  const selectedActionIds = selectedNode?.allowed_actions || []
  const validActions = snapshot?.valid_actions || []
  const validActionIds = new Set(validActions.map((action) => action.id))
  const actions = selectedActionIds.length > 0
    ? selectedActionIds.map((actionId) => actionById.get(actionId) || { id: actionId, label: actionId }).slice(0, 10)
    : validActions.slice(0, 10)
  const flow = useMemo(
    () => mode === 'focus'
      ? buildFocusFlow(nodesById, edges, currentNodeId)
      : buildFullFlow(nodes, edges, currentNodeId, snapshot?.executed_nodes || []),
    [currentNodeId, edges, mode, nodes, nodesById, snapshot?.executed_nodes],
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
          <div className="font-semibold text-slate-900 dark:text-white">{mode === 'focus' ? 'Route graph' : 'Full site graph'}</div>
          <div className="mt-1 text-slate-500 dark:text-slate-400">{graphManifest.version} - {nodes.length} nodes - {graphManifest.actions?.length || 0} actions</div>
        </div>
        <div className="flex items-center gap-2">
          <div className="inline-flex rounded-full border border-slate-200 bg-slate-100 p-0.5 dark:border-white/10 dark:bg-white/[0.04]">
            {(['focus', 'full'] as MapMode[]).map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => setMode(item)}
                className={cx(
                  'rounded-full px-3 py-1.5 text-xs font-semibold transition',
                  mode === item
                    ? 'bg-white text-slate-950 shadow-sm dark:bg-white dark:text-slate-950'
                    : 'text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white',
                )}
              >
                {item === 'focus' ? 'Focus' : 'Full graph'}
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

      <div className="h-[28rem] overflow-hidden rounded-2xl border border-slate-200 bg-slate-950 shadow-inner dark:border-white/10">
        <ReactFlow
          nodes={flow.nodes}
          edges={flow.edges}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.24 }}
          minZoom={0.25}
          maxZoom={2}
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
          <Controls showInteractive={false} />
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

        {validActions.length > 0 && (
          <div>
            <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Current valid controls</div>
            <div className="flex flex-wrap gap-2">
              {validActions.map((action) => {
                const requiresPayload = (action.fields || []).length > 0
                return (
                  <button
                    key={action.id}
                    type="button"
                    disabled={!onActionSelect || requiresPayload || Boolean(action.disabled_reason)}
                    title={requiresPayload ? 'Use the structured form in the main action area.' : action.description || action.id}
                    onClick={() => onActionSelect?.(action)}
                    className={cx(
                      'rounded-full border px-3 py-1.5 text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-50',
                      action.emphasis === 'primary'
                        ? 'border-sky-300 bg-sky-50 text-sky-800 hover:bg-sky-100 dark:border-sky-500/40 dark:bg-sky-500/10 dark:text-sky-200'
                        : 'border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100 dark:border-white/10 dark:bg-white/[0.05] dark:text-slate-300 dark:hover:bg-white/[0.09]',
                    )}
                  >
                    {action.label}
                  </button>
                )
              })}
            </div>
          </div>
        )}

        <div>
          <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Allowed actions</div>
          <div className="flex flex-wrap gap-2">
            {actions.length > 0 ? actions.map((action) => (
              <ActionPill key={action.id} action={action} valid={validActionIds.has(action.id) || selectedActionIds.includes(action.id)} />
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
