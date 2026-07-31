import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
} from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlow,
  type ReactFlowInstance,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { FrontendContract } from "@routedeck/core";

import {
  buildNavGraphTopology,
  bundleNavGraphEdges,
  navGraphEdgesFromContract,
  NAVGRAPH_NODE_HEIGHT,
  NAVGRAPH_NODE_WIDTH,
  type NavGraphInspectorEdge,
} from "./topology";
import { InspectorSection, Legend } from "./components";
import { edgeTypes, type InspectorFlowEdge } from "./edge";
import { routeNavGraphEdges } from "./edgeRouting";
import {
  nodeTypes,
  toneColor,
  type InspectorFlowNode,
  type InspectorNodeData,
  type NodeTone,
} from "./node";
import {
  activePillStyle,
  canvasStyle,
  codeStyle,
  detailsHeaderStyle,
  detailsStyle,
  factsStyle,
  headerStyle,
  legalPillStyle,
  legendStyle,
  pillListStyle,
  pillStyle,
  transitionListStyle,
} from "./styles";

export interface NavGraphInspectorProps {
  contract: FrontendContract;
  edges?: readonly NavGraphInspectorEdge[];
  canvasHeight?: CSSProperties["height"];
  currentNodeId?: string | null;
  reachableNodeIds?: readonly string[];
  activeSurfaceIds?: readonly string[];
  legalOperationIds?: readonly string[];
  showMiniMap?: boolean;
  className?: string;
  onFocusChange?: (nodeId: string) => void;
}

// Fit the complete sitemap when it is larger than the viewport, but never
// enlarge cards beyond their authored size in a roomy/fullscreen canvas.
const FIT_VIEW_OPTIONS = { padding: 0.2, maxZoom: 1 } as const;

export function NavGraphInspectorView({
  contract,
  edges,
  canvasHeight = "26rem",
  currentNodeId = null,
  reachableNodeIds = [],
  activeSurfaceIds = [],
  legalOperationIds = [],
  showMiniMap = true,
  className,
  onFocusChange,
}: NavGraphInspectorProps) {
  const graphEdges = useMemo(
    () => (edges === undefined ? navGraphEdgesFromContract(contract) : [...edges]),
    [contract, edges],
  );
  const topology = useMemo(
    () => buildNavGraphTopology(contract, graphEdges),
    [contract, graphEdges],
  );
  const reachable = useMemo(() => new Set(reachableNodeIds), [reachableNodeIds]);
  const activeSurfaces = useMemo(
    () => new Set(activeSurfaceIds),
    [activeSurfaceIds],
  );
  const legalOperations = useMemo(
    () => new Set(legalOperationIds),
    [legalOperationIds],
  );
  const [focusedNodeId, setFocusedNodeId] = useState<string | null>(
    currentNodeId ?? contract.entry_node_id,
  );
  const flowInstance = useRef<
    ReactFlowInstance<InspectorFlowNode, InspectorFlowEdge> | null
  >(null);
  const canvasElement = useRef<HTMLDivElement | null>(null);
  const fitFrame = useRef<number | null>(null);

  useEffect(() => {
    if (currentNodeId !== null) setFocusedNodeId(currentNodeId);
  }, [currentNodeId]);

  const focusNode = useCallback(
    (nodeId: string) => {
      setFocusedNodeId(nodeId);
      onFocusChange?.(nodeId);
    },
    [onFocusChange],
  );
  const fitGraph = useCallback(() => {
    if (flowInstance.current === null) return;
    if (fitFrame.current !== null) cancelAnimationFrame(fitFrame.current);
    fitFrame.current = requestAnimationFrame(() => {
      fitFrame.current = null;
      void flowInstance.current?.fitView(FIT_VIEW_OPTIONS);
    });
  }, []);

  useEffect(() => {
    const canvas = canvasElement.current;
    if (canvas === null || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver((entries) => {
      const bounds = entries[0]?.contentRect;
      if (bounds === undefined || bounds.width === 0 || bounds.height === 0) return;
      fitGraph();
    });
    observer.observe(canvas);
    return () => {
      observer.disconnect();
      if (fitFrame.current !== null) cancelAnimationFrame(fitFrame.current);
    };
  }, [fitGraph]);

  const flowNodes = useMemo<InspectorFlowNode[]>(
    () =>
      topology.nodes.map((layoutNode) => {
        const node = contract.nodes[layoutNode.id]!;
        const tone: NodeTone =
          node.id === currentNodeId
            ? "current"
            : reachable.has(node.id)
              ? "reachable"
              : "idle";
        const surfaceId =
          node.id === currentNodeId
            ? activeSurfaceIds[0] ?? node.surfaces.active
            : node.surfaces.active;
        return {
          id: node.id,
          type: "routedeck",
          position: { x: layoutNode.x, y: layoutNode.y },
          data: {
            id: node.id,
            title: node.title,
            route: node.route_template,
            surfaceId,
            tone,
            focus: focusNode,
            ...(layoutNode.familyLabel === null
              ? {}
              : { familyLabel: layoutNode.familyLabel }),
          },
          draggable: false,
          selectable: true,
          style: {
            width: NAVGRAPH_NODE_WIDTH,
            minHeight: NAVGRAPH_NODE_HEIGHT,
          },
        };
      }),
    [
      activeSurfaceIds,
      contract.nodes,
      currentNodeId,
      focusNode,
      reachable,
      topology.nodes,
    ],
  );
  const flowEdges = useMemo<InspectorFlowEdge[]>(
    () => {
      const visualEdges = bundleNavGraphEdges(topology.edges);
      const structuralConnections = new Set(
        topology.structuralConnections.map(({ from, to }) =>
          JSON.stringify([from, to]),
        ),
      );
      const routes = new Map(
        routeNavGraphEdges(topology.nodes, visualEdges).map((route) => [
          route.id,
          route,
        ]),
      );
      return visualEdges.flatMap((edge) => {
        const active = edge.from === currentNodeId && reachable.has(edge.to);
        const structural = structuralConnections.has(
          JSON.stringify([edge.from, edge.to]),
        );
        if (!active && !structural) return [];
        const route = routes.get(edge.id);
        if (route === undefined) {
          throw new Error(`Navgraph edge ${edge.id} has no resolved route.`);
        }
        return [{
          id: edge.id,
          source: edge.from,
          target: edge.to,
          type: "routedeck",
          animated: active,
          data: {
            active,
            route,
          },
          style: {
            stroke: active ? "#e56545" : "#9aa49e",
            strokeWidth: active ? 2.5 : 1.25,
            opacity: active ? 0.95 : 0.48,
          },
        }];
      });
    },
    [currentNodeId, reachable, topology.edges, topology.structuralConnections],
  );
  const focused = focusedNodeId ? contract.nodes[focusedNodeId] : undefined;
  const focusedTone =
    focused?.id === currentNodeId
      ? "Current"
      : focused !== undefined && reachable.has(focused.id)
        ? "Available next"
        : "Sitemap node";
  const focusedSurfaces = focused
    ? surfaceEntries(contract, focused.id, activeSurfaces)
    : [];
  const outgoing = focused
    ? contract.transitions.filter((transition) => transition.source === focused.id)
    : [];

  return (
    <section className={className} data-routedeck-inspector="read-only">
      <header style={headerStyle}>
        <div>
          <strong style={{ display: "block", fontSize: "0.9rem" }}>
            Navgraph
          </strong>
          <small style={{ color: "#68736d" }}>
            {Object.keys(contract.nodes).length} nodes · {graphEdges.length} transitions
          </small>
        </div>
        <div aria-label="Map legend" style={legendStyle}>
          <Legend color="#176b5b" label="Current" />
          <Legend color="#e56545" label="Available" />
        </div>
      </header>

      <div
        ref={canvasElement}
        aria-label="RouteDeck navigation graph"
        data-routedeck-navgraph-canvas=""
        style={{ ...canvasStyle, height: canvasHeight }}
      >
        <ReactFlow
          nodes={flowNodes}
          edges={flowEdges}
          edgeTypes={edgeTypes}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={FIT_VIEW_OPTIONS}
          minZoom={0.18}
          maxZoom={1.75}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable
          onInit={(instance) => {
            flowInstance.current = instance;
            fitGraph();
          }}
        >
          <Background variant={BackgroundVariant.Dots} gap={18} size={1} />
          {showMiniMap ? (
            <MiniMap
              pannable
              zoomable
              nodeColor={(node) =>
                toneColor((node.data as InspectorNodeData).tone)
              }
            />
          ) : null}
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>

      {focused ? (
        <aside
          aria-live="polite"
          data-routedeck-inspector-focus={focused.id}
          style={detailsStyle}
        >
          <header style={detailsHeaderStyle}>
            <div>
              <small style={{ color: "#68736d" }}>{focusedTone}</small>
              <h3 style={{ margin: "0.1rem 0 0", fontSize: "1rem" }}>
                {focused.title}
              </h3>
            </div>
            <code style={codeStyle}>{focused.id}</code>
          </header>

          <dl style={factsStyle}>
            <div>
              <dt>Route</dt>
              <dd>{focused.route_template}</dd>
            </div>
            <div>
              <dt>Deep link</dt>
              <dd>{focused.deep_link_policy}</dd>
            </div>
          </dl>

          <InspectorSection title="Surfaces">
            <div style={pillListStyle}>
              {focusedSurfaces.map((surface) => (
                <span
                  key={`${surface.slot}:${surface.id}`}
                  data-active-surface={surface.active ? "true" : "false"}
                  style={{
                    ...pillStyle,
                    ...(surface.active ? activePillStyle : {}),
                  }}
                  title={`${surface.component} · ${surface.lifecycle}`}
                >
                  <b>{surface.slot}</b>
                  {surface.id}
                </span>
              ))}
            </div>
          </InspectorSection>

          <InspectorSection title="Operations">
            <div style={pillListStyle}>
              {focused.operation_ids.map((operationId) => {
                const legal =
                  focused.id === currentNodeId && legalOperations.has(operationId);
                return (
                  <span
                    key={operationId}
                    data-legal-operation={legal ? "true" : "false"}
                    style={{ ...pillStyle, ...(legal ? legalPillStyle : {}) }}
                  >
                    {operationId}
                  </span>
                );
              })}
            </div>
          </InspectorSection>

          <InspectorSection title="Outgoing transitions">
            {outgoing.length === 0 ? (
              <small style={{ color: "#68736d" }}>No outgoing transitions.</small>
            ) : (
              <ul style={transitionListStyle}>
                {outgoing.map((transition, index) => (
                  <li
                    key={`${transition.operation_id}:${transition.outcome}:${transition.target}:${index}`}
                  >
                    <span>
                      {transition.operation_id} · {transition.outcome}
                    </span>
                    <strong>
                      → {contract.nodes[transition.target]?.title ?? transition.target}
                    </strong>
                  </li>
                ))}
              </ul>
            )}
          </InspectorSection>
        </aside>
      ) : null}
    </section>
  );
}

function surfaceEntries(
  contract: FrontendContract,
  nodeId: string,
  activeSurfaceIds: ReadonlySet<string>,
) {
  const node = contract.nodes[nodeId]!;
  const activeSurfaceIdsForNode =
    node.surfaces.active === null ? [] : [node.surfaces.active];
  const slots = [
    ["active", activeSurfaceIdsForNode],
    ["frame", node.surfaces.frame ?? []],
    ["peer", node.surfaces.peer ?? []],
    ["detail", node.surfaces.detail ?? []],
    ["form", node.surfaces.form ?? []],
    ["review", node.surfaces.review ?? []],
    ["status", node.surfaces.status ?? []],
    ["error", node.surfaces.error ?? []],
    ["diagnostic", node.surfaces.diagnostic ?? []],
  ] as const;
  return slots.flatMap(([slot, ids]) =>
    ids.map((id) => {
      const surface = contract.surfaces[id]!;
      return {
        slot,
        id,
        component: surface.component,
        lifecycle: surface.lifecycle ?? "ephemeral",
        active: activeSurfaceIds.has(id),
      };
    }),
  );
}
