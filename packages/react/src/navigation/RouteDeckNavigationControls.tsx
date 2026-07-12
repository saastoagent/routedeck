import { useCallback, useState } from "react";

import {
  useRouteDeckNavigation,
  useRouteDeckNavigationRecovery,
} from "../hooks/navigation";
import { useRouteDeckRuntime } from "../provider/RouteDeckProvider";

export interface RouteDeckNavigationControlsProps {
  className?: string;
}

export function RouteDeckNavigationControls({
  className,
}: RouteDeckNavigationControlsProps) {
  const navigation = useRouteDeckNavigation();
  const recovery = useRouteDeckNavigationRecovery();
  const actions = useRouteDeckRuntime().navigationActions;
  const [error, setError] = useState<Error | null>(null);
  const invoke = useCallback(async (action: (() => void | Promise<void>) | null | undefined) => {
    setError(null);
    try {
      await action?.();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught
          : new Error("The RouteDeck navigation action failed."),
      );
    }
  }, []);
  const back = useCallback(() => void invoke(actions?.back), [actions, invoke]);
  const forward = useCallback(() => void invoke(actions?.forward), [actions, invoke]);
  const cancel = useCallback(() => void invoke(actions?.cancel), [actions, invoke]);

  if (navigation === null) return null;
  return (
    <nav className={className} aria-label="RouteDeck history">
      {recovery.pending === null ? null : (
        <div role="alert" data-routedeck-navigation-recovery="">
          <span>Navigation outcome unknown</span>
          <button
            type="button"
            disabled={recovery.retry === null}
            onClick={() => void invoke(recovery.retry)}
          >
            Retry exact navigation
          </button>
          <button
            type="button"
            disabled={recovery.abandon === null}
            onClick={() => void invoke(recovery.abandon)}
          >
            Abandon and resync
          </button>
        </div>
      )}
      <button
        type="button"
        onClick={back}
        disabled={
          recovery.pending !== null || !navigation.can_back || !actions?.back
        }
      >
        Back
      </button>
      <button
        type="button"
        onClick={forward}
        disabled={
          recovery.pending !== null || !navigation.can_forward || !actions?.forward
        }
      >
        Forward
      </button>
      <button
        type="button"
        onClick={cancel}
        disabled={
          recovery.pending !== null || !navigation.can_cancel || !actions?.cancel
        }
      >
        Cancel
      </button>
      {error === null ? null : <p role="alert">{error.message}</p>}
    </nav>
  );
}
