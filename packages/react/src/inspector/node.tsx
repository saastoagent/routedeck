import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";

import { NAVGRAPH_NODE_HEIGHT, NAVGRAPH_NODE_WIDTH } from "./topology";

export type NodeTone = "current" | "reachable" | "idle";

export interface InspectorNodeData extends Record<string, unknown> {
  id: string;
  title: string;
  route: string;
  surfaceId: string | null;
  tone: NodeTone;
  familyLabel?: string;
  focus: (nodeId: string) => void;
}

export type InspectorFlowNode = Node<InspectorNodeData, "routedeck">;

export const nodeTypes = { routedeck: InspectorNode };

const HIDDEN_HANDLE_STYLE = {
  width: 1,
  height: 1,
  minWidth: 1,
  minHeight: 1,
  border: 0,
  background: "transparent",
  opacity: 0,
} as const;

function InspectorNode({ data, selected }: NodeProps<InspectorFlowNode>) {
  const color = toneColor(data.tone);
  return (
    <button
      type="button"
      aria-label={data.title}
      onClick={() => data.focus(data.id)}
      data-routedeck-navgraph-node={data.id}
      data-node-tone={data.tone}
      style={{
        position: "relative",
        width: NAVGRAPH_NODE_WIDTH,
        minHeight: NAVGRAPH_NODE_HEIGHT,
        border: `${data.tone === "current" ? 3 : 2}px solid ${color}`,
        borderRadius: 14,
        background: data.tone === "current" ? "#176b5b" : "#ffffff",
        padding: "0.65rem 0.75rem",
        font: "inherit",
        textAlign: "left",
        boxShadow: selected
          ? `0 0 0 4px ${color}2f, 0 12px 28px rgba(24, 40, 32, 0.18)`
          : "0 8px 20px rgba(24, 40, 32, 0.1)",
        color: data.tone === "current" ? "#ffffff" : "#17201c",
      }}
    >
      {data.familyLabel === undefined ? null : (
        <code
          style={{
            position: "absolute",
            top: -25,
            left: 2,
            color: "#5e6b64",
            fontSize: 10,
            fontWeight: 800,
            letterSpacing: "0.04em",
          }}
        >
          {data.familyLabel}
        </code>
      )}
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
        {data.surfaceId === null
          ? "Conversation only"
          : `Surface · ${data.surfaceId}`}
      </small>
      <Handle
        type="source"
        position={Position.Bottom}
        style={HIDDEN_HANDLE_STYLE}
      />
    </button>
  );
}

export function toneColor(tone: NodeTone): string {
  if (tone === "current") return "#176b5b";
  if (tone === "reachable") return "#e56545";
  return "#8a958e";
}
