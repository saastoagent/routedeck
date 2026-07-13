import { useCallback, useEffect, useState } from "react";
import {
  RouteDeckError,
  RouteDeckNavGraph,
  RouteDeckStatus,
  useRouteDeckClientError,
  useRouteDeckMutationRecovery,
  useRouteDeckProjection,
} from "@routedeck/react";

import "./navgraph-sidebar.css";

const NAVGRAPH_LABEL = "Navgraph";
const NAVGRAPH_PANEL_ID = "medusa-navgraph-sidebar";
const RECOVERY_FAILURE_CODE = "mutation_recovery_failed";

export function NavgraphSidebar() {
  const projection = useRouteDeckProjection();
  const clientError = useRouteDeckClientError();
  const mutationRecovery = useRouteDeckMutationRecovery();
  const [expanded, setExpanded] = useState(false);
  const [recoveryError, setRecoveryError] = useState<Error | null>(null);
  const hasFailure =
    clientError !== null ||
    (projection?.failure !== null && projection?.failure !== undefined);

  const close = useCallback(() => setExpanded(false), []);
  const recover = useCallback(async (action: () => Promise<unknown>) => {
    setRecoveryError(null);
    try {
      await action();
    } catch (caught) {
      setRecoveryError(
        caught instanceof Error
          ? caught
          : new Error("The RouteDeck mutation recovery failed."),
      );
    }
  }, []);

  useEffect(() => {
    if (!expanded) return undefined;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [close, expanded]);

  return (
    <aside
      className="navgraph-sidebar"
      data-expanded={expanded ? "true" : "false"}
      data-status={hasFailure ? "error" : projection === null ? "idle" : "live"}
      aria-label={NAVGRAPH_LABEL}
    >
      <button
        type="button"
        className="navgraph-sidebar-toggle"
        aria-controls={NAVGRAPH_PANEL_ID}
        aria-expanded={expanded}
        aria-label={`${expanded ? "Close" : "Open"} ${NAVGRAPH_LABEL}`}
        onClick={() => setExpanded((current) => !current)}
      >
        <NavgraphIcon />
        <span>{expanded ? "Close" : NAVGRAPH_LABEL}</span>
        <i aria-hidden="true" />
      </button>

      <div
        id={NAVGRAPH_PANEL_ID}
        className="navgraph-sidebar-panel"
        hidden={!expanded}
      >
        <header className="navgraph-sidebar-heading">
          <div>
            <h2>{NAVGRAPH_LABEL}</h2>
            <p>Full sitemap with live nodes, operations, and surfaces.</p>
          </div>
        </header>

        <RouteDeckStatus className="navgraph-status">
          {({ code, message, syncStatus }) => (
            <>
              <span>{message ?? code}</span>
              <small>{syncStatus}</small>
            </>
          )}
        </RouteDeckStatus>

        {projection === null ? null : (
          <dl className="navgraph-session-facts">
            <div>
              <dt>Active node</dt>
              <dd>{projection.current.node_id}</dd>
            </div>
            <div>
              <dt>Session</dt>
              <dd>v{projection.session_version}</dd>
            </div>
            <div>
              <dt>Projection</dt>
              <dd>v{projection.projection_version}</dd>
            </div>
          </dl>
        )}

        <RouteDeckNavGraph className="navgraph-map" />

        {projection?.failure === null || projection?.failure === undefined ? null : (
          <RouteDeckError failure={projection.failure} className="navgraph-error" />
        )}
        {clientError === null ? null : (
          <RouteDeckError
            code={clientError.code}
            message={clientError.message}
            className="navgraph-error"
          />
        )}
        {mutationRecovery.pending === null ? null : (
          <section role="alert" className="navgraph-recovery">
            <strong>Mutation outcome unknown</strong>
            <small>{mutationRecovery.pending.fingerprint}</small>
            <div>
              <button
                type="button"
                disabled={mutationRecovery.retrying}
                onClick={() => void recover(mutationRecovery.retry)}
              >
                Retry exact mutation
              </button>
              <button
                type="button"
                disabled={mutationRecovery.retrying}
                onClick={() => void recover(mutationRecovery.abandon)}
              >
                Abandon and resync
              </button>
            </div>
          </section>
        )}
        {recoveryError === null ? null : (
          <RouteDeckError
            code={RECOVERY_FAILURE_CODE}
            message={recoveryError.message}
            className="navgraph-error"
          />
        )}
      </div>
    </aside>
  );
}

function NavgraphIcon() {
  return (
    <svg
      aria-hidden="true"
      className="navgraph-sidebar-icon"
      viewBox="0 0 24 24"
      fill="none"
    >
      <path d="M7 6.5h10M7 17.5h10M7 6.5l5 11 5-11" />
      <circle cx="7" cy="6.5" r="2.25" />
      <circle cx="17" cy="6.5" r="2.25" />
      <circle cx="12" cy="17.5" r="2.25" />
    </svg>
  );
}
