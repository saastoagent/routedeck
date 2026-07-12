import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { createPortal } from "react-dom";

import { useRouteDeckContract, useRouteDeckProjection } from "../hooks/projection";
import { NavGraphInspector } from "./lazy";

export interface RouteDeckNavGraphProps {
  className?: string;
  onFocusChange?: (nodeId: string) => void;
}

export function RouteDeckNavGraph({
  className,
  onFocusChange,
}: RouteDeckNavGraphProps) {
  const contract = useRouteDeckContract();
  const projection = useRouteDeckProjection();
  const currentNodeId = projection?.current.node_id ?? contract.entry_node_id;
  const [expanded, setExpanded] = useState(false);
  const legalOperationIds = useMemo(
    () =>
      projection?.legal_operations.map((operation) => operation.operation_id) ?? [],
    [projection?.legal_operations],
  );
  const reachableNodeIds = useMemo(() => {
    const legal = new Set(legalOperationIds);
    return Array.from(
      new Set(
        contract.transitions
          .filter(
            (transition) =>
              transition.source === currentNodeId &&
              legal.has(transition.operation_id),
          )
          .map((transition) => transition.target),
      ),
    );
  }, [contract.transitions, currentNodeId, legalOperationIds]);
  const activeSurfaceIds = useMemo(() => {
    if (projection === null) return [];
    return [
      projection.surfaces.active,
      ...projection.surfaces.frame,
      ...projection.surfaces.peer,
      ...projection.surfaces.detail,
      ...projection.surfaces.form,
      ...projection.surfaces.review,
      ...projection.surfaces.status,
      ...projection.surfaces.error,
      ...projection.surfaces.diagnostic,
    ].map((surface) => surface.surface_id);
  }, [projection]);

  useEffect(() => {
    if (!expanded) return undefined;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setExpanded(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [expanded]);

  const inspectorProps = {
    contract,
    currentNodeId,
    reachableNodeIds,
    activeSurfaceIds,
    legalOperationIds,
    ...(onFocusChange === undefined ? {} : { onFocusChange }),
  };

  return (
    <>
      <section
        data-routedeck-navgraph-shell=""
        {...(className === undefined ? {} : { className })}
      >
        <div
          aria-label="Navgraph controls"
          data-routedeck-navgraph-toolbar=""
          style={toolbarStyle}
        >
          <button
            type="button"
            onClick={() => setExpanded(true)}
            style={expandButtonStyle}
          >
            Expand
          </button>
        </div>
        <NavGraphInspector
          {...inspectorProps}
          canvasHeight="25rem"
        />
      </section>

      {expanded && typeof document !== "undefined"
        ? createPortal(
            <div
              role="dialog"
              aria-modal="true"
              aria-label="RouteDeck navgraph"
              data-routedeck-navgraph-dialog=""
              style={dialogBackdropStyle}
            >
              <section style={dialogPanelStyle}>
                <header style={dialogHeaderStyle}>
                  <div>
                    <strong style={{ display: "block", fontSize: "1rem" }}>
                      RouteDeck Navgraph
                    </strong>
                    <small style={{ color: "#68736d" }}>
                      Live nodes, transitions, legal operations, and surfaces
                    </small>
                  </div>
                  <button
                    type="button"
                    onClick={() => setExpanded(false)}
                    style={expandButtonStyle}
                  >
                    Close
                  </button>
                </header>
                <NavGraphInspector
                  {...inspectorProps}
                  canvasHeight="calc(100vh - 15rem)"
                />
              </section>
            </div>,
            document.body,
          )
        : null}
    </>
  );
}

const toolbarStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "flex-end",
  gap: "0.65rem",
  marginBottom: "0.7rem",
};
const expandButtonStyle: CSSProperties = {
  minHeight: 32,
  border: "1px solid #bdc8c1",
  borderRadius: 999,
  background: "#ffffff",
  padding: "0.35rem 0.65rem",
  color: "#34423b",
  fontSize: "0.7rem",
  fontWeight: 750,
};
const dialogBackdropStyle: CSSProperties = {
  position: "fixed",
  zIndex: 100,
  inset: 0,
  overflow: "auto",
  background: "rgba(18, 28, 23, 0.58)",
  padding: "clamp(0.75rem, 2vw, 1.5rem)",
  backdropFilter: "blur(10px)",
};
const dialogPanelStyle: CSSProperties = {
  width: "min(96rem, 100%)",
  minHeight: "calc(100vh - 3rem)",
  margin: "0 auto",
  border: "1px solid rgba(255, 255, 255, 0.42)",
  borderRadius: 20,
  background: "#eef1ed",
  padding: "clamp(0.9rem, 2vw, 1.5rem)",
  boxShadow: "0 30px 80px rgba(10, 20, 15, 0.3)",
};
const dialogHeaderStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "1rem",
  marginBottom: "0.9rem",
};
