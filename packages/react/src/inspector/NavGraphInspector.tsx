import { useEffect, useMemo, useState, type CSSProperties } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { FrontendContract } from "@routedeck/core";

import {
  buildNavGraphTopology,
  navGraphEdgesFromContract,
  NAVGRAPH_NODE_HEIGHT,
  NAVGRAPH_NODE_WIDTH,
  type NavGraphInspectorEdge,
} from "./topology";

export interface NavGraphInspectorProps {
  contract: FrontendContract;
  edges?: readonly NavGraphInspectorEdge[];
  canvasHeight?: CSSProperties["height"];
  currentNodeId?: string | null;
  reachableNodeIds?: readonly string[];
  activeSurfaceIds?: readonly string[];
  legalOperationIds?: readonly string[];
  className?: string;
  onFocusChange?: (nodeId: string) => void;
}

type NodeTone = "current" | "reachable" | "idle";

interface InspectorNodeData extends Record<string, unknown> {
  id: string;
  title: string;
  route: string;
  surfaceId: string;
  tone: NodeTone;
}

type InspectorFlowNode = Node<InspectorNodeData, "routedeck">;

const nodeTypes = { routedeck: InspectorNode };
const HIDDEN_HANDLE_STYLE: CSSProperties = {
  width: 1,
  height: 1,
  minWidth: 1,
  minHeight: 1,
  border: 0,
  background: "transparent",
  opacity: 0,
};

export function NavGraphInspectorView({
  contract,
  edges,
  canvasHeight = "26rem",
  currentNodeId = null,
  reachableNodeIds = [],
  activeSurfaceIds = [],
  legalOperationIds = [],
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

  useEffect(() => {
    if (currentNodeId !== null) setFocusedNodeId(currentNodeId);
  }, [currentNodeId]);

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
          },
          draggable: false,
          selectable: true,
          style: {
            width: NAVGRAPH_NODE_WIDTH,
            minHeight: NAVGRAPH_NODE_HEIGHT,
          },
        };
      }),
    [activeSurfaceIds, contract.nodes, currentNodeId, reachable, topology.nodes],
  );
  const flowEdges = useMemo<Edge[]>(
    () =>
      topology.edges.map((edge) => {
        const active = edge.from === currentNodeId && reachable.has(edge.to);
        return {
          id: edge.id,
          source: edge.from,
          target: edge.to,
          type: "smoothstep",
          animated: active,
          ...(active && edge.label !== undefined ? { label: edge.label } : {}),
          style: {
            stroke: active ? "#e56545" : "#9aa49e",
            strokeWidth: active ? 2.5 : 1.25,
            opacity: active ? 0.95 : 0.48,
          },
          labelStyle: {
            fill: "#513226",
            fontSize: 9,
            fontWeight: 700,
          },
          labelBgStyle: {
            fill: "#fcebe6",
            fillOpacity: 0.96,
          },
        };
      }),
    [currentNodeId, reachable, topology.edges],
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

  const focusNode = (nodeId: string) => {
    setFocusedNodeId(nodeId);
    onFocusChange?.(nodeId);
  };

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
        aria-label="RouteDeck navigation graph"
        data-routedeck-navgraph-canvas=""
        style={{ ...canvasStyle, height: canvasHeight }}
      >
        <ReactFlow
          nodes={flowNodes}
          edges={flowEdges}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          minZoom={0.18}
          maxZoom={1.75}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable
          onNodeClick={(_event, node) => focusNode(node.id)}
        >
          <Background variant={BackgroundVariant.Dots} gap={18} size={1} />
          <MiniMap
            pannable
            zoomable
            nodeColor={(node) => toneColor((node.data as InspectorNodeData).tone)}
          />
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

function InspectorNode({ data, selected }: NodeProps<InspectorFlowNode>) {
  const color = toneColor(data.tone);
  return (
    <div
      data-routedeck-navgraph-node={data.id}
      data-node-tone={data.tone}
      style={{
        width: NAVGRAPH_NODE_WIDTH,
        minHeight: NAVGRAPH_NODE_HEIGHT,
        border: `${data.tone === "current" ? 3 : 2}px solid ${color}`,
        borderRadius: 14,
        background: data.tone === "current" ? "#176b5b" : "#ffffff",
        padding: "0.65rem 0.75rem",
        boxShadow: selected
          ? `0 0 0 4px ${color}2f, 0 12px 28px rgba(24, 40, 32, 0.18)`
          : "0 8px 20px rgba(24, 40, 32, 0.1)",
        color: data.tone === "current" ? "#ffffff" : "#17201c",
      }}
    >
      <Handle type="target" position={Position.Top} style={HIDDEN_HANDLE_STYLE} />
      <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
        <strong style={{ minWidth: 0, fontSize: 13 }}>{data.title}</strong>
        <span
          style={{
            flex: "0 0 auto",
            borderRadius: 999,
            background: data.tone === "current" ? "#ffffff" : `${color}18`,
            padding: "0.1rem 0.35rem",
            color: data.tone === "current" ? "#176b5b" : color,
            fontSize: 8,
            fontWeight: 800,
            letterSpacing: "0.05em",
            textTransform: "uppercase",
          }}
        >
          {data.tone === "current"
            ? "You are here"
            : data.tone === "reachable"
              ? "Available"
              : "Node"}
        </span>
      </div>
      <code
        style={{
          display: "block",
          marginTop: 5,
          overflow: "hidden",
          fontSize: 9,
          opacity: 0.72,
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {data.route}
      </code>
      <small
        style={{
          display: "block",
          marginTop: 5,
          overflow: "hidden",
          fontSize: 9,
          opacity: 0.82,
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        Surface · {data.surfaceId}
      </small>
      <Handle type="source" position={Position.Bottom} style={HIDDEN_HANDLE_STYLE} />
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
      <span
        aria-hidden="true"
        style={{ width: 7, height: 7, borderRadius: "50%", background: color }}
      />
      {label}
    </span>
  );
}

function InspectorSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section style={{ marginTop: "0.85rem" }}>
      <h4 style={sectionTitleStyle}>{title}</h4>
      {children}
    </section>
  );
}

function surfaceEntries(
  contract: FrontendContract,
  nodeId: string,
  activeSurfaceIds: ReadonlySet<string>,
) {
  const node = contract.nodes[nodeId]!;
  const slots = [
    ["active", [node.surfaces.active]],
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

function toneColor(tone: NodeTone) {
  if (tone === "current") return "#176b5b";
  if (tone === "reachable") return "#e56545";
  return "#8a958e";
}

const headerStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "0.75rem",
  marginBottom: "0.7rem",
};
const legendStyle: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  justifyContent: "flex-end",
  gap: "0.4rem 0.65rem",
  color: "#68736d",
  fontSize: "0.65rem",
};
const canvasStyle: CSSProperties = {
  width: "100%",
  height: "26rem",
  minHeight: 320,
  overflow: "hidden",
  border: "1px solid #d9dfda",
  borderRadius: 14,
  background: "#f7f9f6",
};
const detailsStyle: CSSProperties = {
  marginTop: "0.75rem",
  border: "1px solid #d9dfda",
  borderRadius: 14,
  background: "#ffffff",
  padding: "0.85rem",
};
const detailsHeaderStyle: CSSProperties = {
  display: "flex",
  alignItems: "start",
  justifyContent: "space-between",
  gap: "0.75rem",
};
const codeStyle: CSSProperties = {
  maxWidth: "52%",
  overflow: "hidden",
  borderRadius: 6,
  background: "#eef1ed",
  padding: "0.2rem 0.35rem",
  color: "#34423b",
  fontSize: "0.62rem",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};
const factsStyle: CSSProperties = {
  display: "grid",
  gap: "0.35rem",
  margin: "0.75rem 0 0",
};
const sectionTitleStyle: CSSProperties = {
  margin: "0 0 0.4rem",
  color: "#68736d",
  fontSize: "0.64rem",
  letterSpacing: "0.07em",
  textTransform: "uppercase",
};
const pillListStyle: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: "0.35rem",
};
const pillStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: "0.3rem",
  maxWidth: "100%",
  overflow: "hidden",
  borderWidth: 1,
  borderStyle: "solid",
  borderColor: "#d9dfda",
  borderRadius: 999,
  background: "#f7f9f6",
  padding: "0.22rem 0.45rem",
  color: "#34423b",
  fontSize: "0.62rem",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};
const activePillStyle: CSSProperties = {
  borderColor: "#82b6a6",
  background: "#e4f2ed",
  color: "#0f4f44",
};
const legalPillStyle: CSSProperties = {
  borderColor: "#e5a28f",
  background: "#fcebe6",
  color: "#753423",
};
const transitionListStyle: CSSProperties = {
  display: "grid",
  gap: "0.35rem",
  margin: 0,
  padding: 0,
  listStyle: "none",
  fontSize: "0.67rem",
};
