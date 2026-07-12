import type { ReactNode } from "react";
import type { RouteDeckFailure } from "@routedeck/core";

export interface RouteDeckErrorProps {
  failure?: RouteDeckFailure | null;
  code?: string;
  message?: ReactNode;
  correlationId?: string | null;
  className?: string;
}

export function RouteDeckError({
  failure,
  code,
  message,
  correlationId,
  className,
}: RouteDeckErrorProps) {
  const resolvedCode = failure?.code ?? code ?? "routedeck_error";
  const resolvedMessage =
    failure?.public_message ?? message ?? "RouteDeck could not render this state.";
  const resolvedCorrelationId =
    failure?.correlation_id ?? correlationId ?? null;
  return (
    <section
      className={className}
      role="alert"
      data-routedeck-error={resolvedCode}
    >
      <p>{resolvedMessage}</p>
      {resolvedCorrelationId === null ? null : (
        <small>Reference: {resolvedCorrelationId}</small>
      )}
    </section>
  );
}
