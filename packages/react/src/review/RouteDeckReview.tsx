import { useCallback, useState, type ReactNode } from "react";

import { useRouteDeckReviewActions } from "../hooks/operations";
import { RouteDeckError } from "../status/RouteDeckError";

export interface RouteDeckReviewProps {
  reviewId: string;
  title?: ReactNode;
  children?: ReactNode;
  acceptLabel?: ReactNode;
  rejectLabel?: ReactNode;
  acceptDisabled?: boolean;
  className?: string;
  onResolved?: (decision: "accepted" | "rejected") => void;
}

export function RouteDeckReview({
  reviewId,
  title = "Review required",
  children,
  acceptLabel = "Accept",
  rejectLabel = "Reject",
  acceptDisabled = false,
  className,
  onResolved,
}: RouteDeckReviewProps) {
  const actions = useRouteDeckReviewActions();
  const [pending, setPending] = useState<"accept" | "reject" | null>(null);
  const [error, setError] = useState<Error | null>(null);

  const decide = useCallback(
    async (decision: "accept" | "reject") => {
      setPending(decision);
      setError(null);
      try {
        if (decision === "accept") await actions.accept(reviewId);
        else await actions.reject(reviewId);
        onResolved?.(decision === "accept" ? "accepted" : "rejected");
      } catch (caught) {
        setError(
          caught instanceof Error
            ? caught
            : new Error("The RouteDeck review decision failed."),
        );
      } finally {
        setPending(null);
      }
    },
    [actions, reviewId, onResolved],
  );

  return (
    <section className={className} aria-labelledby={`review-${reviewId}`}>
      <h2 id={`review-${reviewId}`}>{title}</h2>
      {children}
      {error === null ? null : (
        <RouteDeckError code="review_failed" message={error.message} />
      )}
      <div>
        <button
          type="button"
          disabled={acceptDisabled || pending !== null}
          onClick={() => void decide("accept")}
        >
          {pending === "accept" ? "Accepting…" : acceptLabel}
        </button>
        <button
          type="button"
          disabled={pending !== null}
          onClick={() => void decide("reject")}
        >
          {pending === "reject" ? "Rejecting…" : rejectLabel}
        </button>
      </div>
    </section>
  );
}
