import { useCallback, useEffect, useState, useSyncExternalStore } from "react";

import type { RouteDeckStore } from "@routedeck/core";

export interface BootstrapRecoveryShellProps {
  store: RouteDeckStore;
  onReady(): void;
}

export function BootstrapRecoveryShell({
  store,
  onReady,
}: BootstrapRecoveryShellProps) {
  const state = useSyncExternalStore(
    store.subscribe,
    store.getState,
    store.getState,
  );
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const pendingBootstrap = state.pendingBootstrap;
  const pendingNavigation = state.pendingNavigation;
  const expired = pendingBootstrap?.kind === "resume_expired";
  const missing = pendingBootstrap?.kind === "resume_missing";
  const incompatible = pendingBootstrap?.kind === "resume_incompatible";
  const canReconnectCurrent =
    pendingBootstrap === null && pendingNavigation === null;
  const canStartNew =
    pendingBootstrap?.kind === "session_create" ||
    expired ||
    missing ||
    incompatible;

  useEffect(() => {
    if (state.syncStatus === "live") onReady();
  }, [onReady, state.syncStatus]);

  const recover = useCallback(
    async (action: () => Promise<void>) => {
      setBusy(true);
      setActionError(null);
      try {
        await action();
        if (store.getState().syncStatus !== "live") {
          throw new Error(
            "RouteDeck recovery completed without a live buyer session.",
          );
        }
        setBusy(false);
      } catch (error) {
        setBusy(false);
        setActionError(
          error instanceof Error
            ? error.message
            : "RouteDeck could not recover the buyer session.",
        );
      }
    },
    [store],
  );

  return (
    <section className="bootstrap-error" role="alert">
      <h1>
        {expired
          ? "Buyer session expired"
          : missing
            ? "Buyer session unavailable"
            : incompatible
              ? "Buyer session incompatible"
            : "Medusa Agent needs session recovery"}
      </h1>
      <p>
        {expired
          ? "The saved buyer session is no longer available. Start a new session explicitly to continue."
          : missing
            ? "This session-bound link has no available buyer session. Start a new session explicitly to continue."
            : incompatible
              ? "The application contract changed. Start a new buyer session explicitly to continue."
            : (actionError ??
            state.error?.message ??
            "The buyer session did not finish starting.")}
      </p>
      {pendingBootstrap?.kind === "session_create" ? (
        <p>
          Session creation may already have committed. Retrying securely reuses
          the retained recovery request.
        </p>
      ) : null}
      {pendingNavigation !== null ? (
        <p>
          The requested route may already be open. Retry that exact navigation
          or abandon it and load the authoritative session.
        </p>
      ) : null}
      <div className="bootstrap-actions">
        {pendingBootstrap?.kind === "session_create" ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => void recover(store.retrySessionCreate)}
          >
            Retry creating this buyer session
          </button>
        ) : null}
        {pendingNavigation !== null ? (
          <>
            <button
              type="button"
              disabled={busy}
              onClick={() => void recover(store.retryNavigation)}
            >
              Retry opening this route
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void recover(store.abandonNavigation)}
            >
              Abandon route and use current session
            </button>
          </>
        ) : null}
        {canReconnectCurrent ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => void recover(store.resync)}
          >
            Reconnect current buyer session
          </button>
        ) : null}
        {canStartNew ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => void recover(store.startNewSession)}
          >
            Start a new buyer session
          </button>
        ) : null}
      </div>
      {expired && actionError !== null ? <p>{actionError}</p> : null}
    </section>
  );
}
