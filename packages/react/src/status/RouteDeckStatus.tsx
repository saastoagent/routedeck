import type { ReactNode } from "react";

import {
  useRouteDeckClientError,
  useRouteDeckStatus,
  useRouteDeckSyncStatus,
} from "../hooks/status";

export interface RouteDeckStatusProps {
  className?: string;
  children?: (status: {
    code: string;
    message: string | null;
    syncStatus: string;
  }) => ReactNode;
}

export function RouteDeckStatus({ className, children }: RouteDeckStatusProps) {
  const projected = useRouteDeckStatus();
  const syncStatus = useRouteDeckSyncStatus();
  const clientError = useRouteDeckClientError();
  const status = {
    code: clientError?.code ?? projected?.code ?? syncStatus,
    message: clientError?.message ?? projected?.message ?? null,
    syncStatus,
  };
  return (
    <div
      className={className}
      role="status"
      aria-live="polite"
      data-routedeck-status={status.code}
    >
      {children ? children(status) : status.message ?? status.code}
    </div>
  );
}
