import { useCallback, useState, type ReactNode } from "react";
import {
  RouteDeckError as RouteDeckClientError,
  type RouteDeckProjectedSuggestedAction,
} from "@routedeck/core";

import { useRouteDeckDispatch, useRouteDeckMutationRecovery } from "../hooks/operations";
import { useRouteDeckProjection } from "../hooks/projection";
import { RouteDeckError } from "../status/RouteDeckError";

const SUGGESTED_ACTION_FAILURE_CODE = "suggested_action_failed";

export interface RouteDeckSuggestedActionsProps {
  className?: string;
  disabled?: boolean;
  empty?: ReactNode;
}
export function RouteDeckSuggestedActions({
  className,
  disabled = false,
  empty = null,
}: RouteDeckSuggestedActionsProps) {
  const projection = useRouteDeckProjection();
  const dispatch = useRouteDeckDispatch();
  const mutation = useRouteDeckMutationRecovery();
  const [pendingActionId, setPendingActionId] = useState<string | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const actions = projection?.suggested_actions ?? [];

  const activate = useCallback(
    async (action: RouteDeckProjectedSuggestedAction) => {
      setPendingActionId(action.action_id);
      setError(null);
      try {
        await dispatch(action.operation_id, action.arguments);
      } catch (caught) {
        if (!(caught instanceof Error)) throw caught;
        setError(caught);
      } finally {
        setPendingActionId(null);
      }
    },
    [dispatch],
  );

  if (actions.length === 0) return <>{empty}</>;

  return (
    <div
      aria-label="Suggested actions"
      aria-busy={mutation.inFlight}
      className={className}
      data-routedeck-suggested-actions=""
    >
      <div role="group">
        {actions.map((action) => (
          <button
            key={action.action_id}
            type="button"
            disabled={disabled || mutation.inFlight}
            data-routedeck-suggested-action={action.action_id}
            onClick={() => void activate(action)}
          >
            {pendingActionId === action.action_id
              ? `${action.label}…`
              : action.label}
          </button>
        ))}
      </div>
      {error === null ? null : (
        <RouteDeckError
          code={
            error instanceof RouteDeckClientError
              ? error.code
              : SUGGESTED_ACTION_FAILURE_CODE
          }
          message={error.message}
        />
      )}
    </div>
  );
}
