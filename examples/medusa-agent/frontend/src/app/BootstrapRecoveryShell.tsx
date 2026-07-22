import type {
  RouteDeckBootstrapActionRequiredState,
  RouteDeckBootstrapDisposedState,
  RouteDeckBootstrapRecoveryActionKind,
} from "@routedeck/react";

export interface BootstrapRecoveryShellProps {
  state:
    | RouteDeckBootstrapActionRequiredState
    | RouteDeckBootstrapDisposedState;
}

export function BootstrapRecoveryShell({
  state,
}: BootstrapRecoveryShellProps) {
  const reason = state.phase === "recovery" ? state.reason : "disposed";
  const expired = reason === "resume_expired";
  const missing = reason === "resume_missing";
  const contractMismatch = reason === "resume_contract_mismatch";
  const sessionCreate = reason === "session_create";
  const navigation = reason === "navigation";
  const action = (kind: RouteDeckBootstrapRecoveryActionKind) =>
    state.actions.find((candidate) => candidate.kind === kind) ?? null;

  return (
    <section className="bootstrap-error" role="alert">
      <h1>
        {expired
          ? "Buyer session expired"
          : missing
            ? "Buyer session unavailable"
            : contractMismatch
              ? "Buyer session contract changed"
              : "Medusa Agent needs session recovery"}
      </h1>
      <p>
        {expired
          ? "The saved buyer session is no longer available. Start a new session explicitly to continue."
          : missing
            ? "This session-bound link has no available buyer session. Start a new session explicitly to continue."
            : contractMismatch
              ? "The application contract changed. Start a new buyer session explicitly to continue."
              : (state.error?.message ??
                "The buyer session did not finish starting.")}
      </p>
      {sessionCreate ? (
        <p>
          Session creation may already have committed. Retrying securely reuses
          the retained recovery request.
        </p>
      ) : null}
      {navigation ? (
        <p>
          The requested route may already be open. Retry that exact navigation
          or abandon it and load the authoritative session.
        </p>
      ) : null}
      <div className="bootstrap-actions">
        <RecoveryButton
          action={action("retry_session_create")}
          disabled={state.busy}
        >
          Retry creating this buyer session
        </RecoveryButton>
        <RecoveryButton
          action={action("retry_navigation")}
          disabled={state.busy}
        >
          Retry opening this route
        </RecoveryButton>
        <RecoveryButton
          action={action("abandon_navigation")}
          disabled={state.busy}
        >
          Abandon route and use current session
        </RecoveryButton>
        <RecoveryButton action={action("resync")} disabled={state.busy}>
          Reconnect current buyer session
        </RecoveryButton>
        <RecoveryButton
          action={action("start_new_session")}
          disabled={state.busy}
        >
          Start a new buyer session
        </RecoveryButton>
      </div>
      {(expired || missing || contractMismatch) && state.error !== null ? (
        <p>{state.error.message}</p>
      ) : null}
    </section>
  );
}

function RecoveryButton({
  action,
  disabled,
  children,
}: {
  action: {
    run(): Promise<void>;
  } | null;
  disabled: boolean;
  children: string;
}) {
  if (action === null) return null;
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => void action.run()}
    >
      {children}
    </button>
  );
}
