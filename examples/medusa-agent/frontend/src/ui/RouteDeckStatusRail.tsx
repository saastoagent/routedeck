import { useCallback, useState } from "react";
import {
  RouteDeckError,
  RouteDeckNavGraph,
  RouteDeckStatus,
  useRouteDeckClientError,
  useRouteDeckMutationRecovery,
  useRouteDeckProjection,
} from "@routedeck/react";

export function RouteDeckStatusRail() {
  const projection = useRouteDeckProjection();
  const clientError = useRouteDeckClientError();
  const mutationRecovery = useRouteDeckMutationRecovery();
  const [recoveryError, setRecoveryError] = useState<Error | null>(null);
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

  return (
    <aside className="routedeck-rail" aria-label="RouteDeck session status">
      <div className="rail-heading">
        <span aria-hidden="true" />
        <strong>RouteDeck</strong>
      </div>
      <RouteDeckStatus className="rail-status">
        {({ code, message, syncStatus }) => (
          <>
            <span>{message ?? code}</span>
            <small>{syncStatus}</small>
          </>
        )}
      </RouteDeckStatus>
      {projection === null ? null : (
        <dl className="rail-facts">
          <div>
            <dt>Node</dt>
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
      <RouteDeckNavGraph className="rail-navgraph" />
      {projection?.failure === null || projection?.failure === undefined ? null : (
        <RouteDeckError failure={projection.failure} className="rail-error" />
      )}
      {clientError === null ? null : (
        <RouteDeckError
          code={clientError.code}
          message={clientError.message}
          className="rail-error"
        />
      )}
      {mutationRecovery.pending === null ? null : (
        <section role="alert" data-routedeck-mutation-recovery="">
          <strong>Mutation outcome unknown</strong>
          <small>{mutationRecovery.pending.fingerprint}</small>
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
        </section>
      )}
      {recoveryError === null ? null : (
        <RouteDeckError
          code="mutation_recovery_failed"
          message={recoveryError.message}
          className="rail-error"
        />
      )}
    </aside>
  );
}
