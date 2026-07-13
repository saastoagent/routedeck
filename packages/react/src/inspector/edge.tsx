import {
  BaseEdge,
  EdgeLabelRenderer,
  type Edge,
  type EdgeProps,
} from "@xyflow/react";

import {
  navGraphEdgeGeometry,
  type NavGraphEdgeRoute,
} from "./edgeRouting";

export interface InspectorEdgeData extends Record<string, unknown> {
  active: boolean;
  label?: string;
  route: NavGraphEdgeRoute;
}

export type InspectorFlowEdge = Edge<InspectorEdgeData, "routedeck">;

export const edgeTypes = { routedeck: InspectorEdge };

function InspectorEdge({
  id,
  data,
  markerEnd,
  style,
}: EdgeProps<InspectorFlowEdge>) {
  if (data === undefined) return null;
  const geometry = navGraphEdgeGeometry(data.route);
  return (
    <>
      <BaseEdge
        id={id}
        path={geometry.path}
        interactionWidth={16}
        {...(markerEnd === undefined ? {} : { markerEnd })}
        {...(style === undefined ? {} : { style })}
      />
      {data.active && data.label !== undefined ? (
        <EdgeLabelRenderer>
          <span
            data-routedeck-navgraph-edge-label={id}
            style={{
              position: "absolute",
              transform: `translate(-50%, -50%) translate(${geometry.labelX}px, ${geometry.labelY}px)`,
              maxWidth: 150,
              overflow: "hidden",
              borderRadius: 4,
              background: "rgba(252, 235, 230, 0.96)",
              padding: "0.12rem 0.28rem",
              color: "#513226",
              fontSize: 9,
              fontWeight: 700,
              pointerEvents: "none",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {data.label}
          </span>
        </EdgeLabelRenderer>
      ) : null}
    </>
  );
}
