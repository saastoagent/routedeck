import { useCallback, useState } from "react";
import type { RouteDeckSurfaceComponentProps } from "@routedeck/react";
import { RouteDeckError, RouteDeckReview } from "@routedeck/react";

import {
  checkoutExactKeys,
  checkoutInvalid,
  checkoutString,
} from "./PaymentMethodSurface";
import { useCheckoutReviewAuthority } from "./CheckoutReviewAuthority";

type CheckoutPlacementProjection =
  | {
      state: "pending";
      review_id: string;
      expires_at: string;
    }
  | {
      state: "external_outcome_unknown";
      message: string;
      correlation_id: string;
      order_ref?: string;
    };

export function CheckoutPlacementSurface({
  props,
  dispatchAffordance,
}: RouteDeckSurfaceComponentProps) {
  if (Object.keys(props).length === 0) return null;
  const placement = decodeCheckoutPlacement(props);
  if (placement.state === "external_outcome_unknown") {
    return (
      <UnknownOrderRecovery
        placement={placement}
        dispatchAffordance={dispatchAffordance}
      />
    );
  }
  return <PendingOrderReview placement={placement} />;
}

function PendingOrderReview({
  placement,
}: {
  placement: Extract<CheckoutPlacementProjection, { state: "pending" }>;
}) {
  const authority = useCheckoutReviewAuthority();
  return (
    <RouteDeckReview
      reviewId={placement.review_id}
      title="Confirm order placement"
      acceptLabel="Place order"
      rejectLabel="Cancel order placement"
      acceptDisabled={authority.state !== "ready"}
    >
      <p>
        Approval uses the frozen order proposal and refreshes authoritative cart
        facts before attempting completion.
      </p>
      <p>Review expires {new Date(placement.expires_at).toLocaleString()}.</p>
      {authority.state === "ready" ? null : (
        <p role="status">
          Place order is unavailable until the private delivery address is
          loaded and verified.
        </p>
      )}
    </RouteDeckReview>
  );
}

function UnknownOrderRecovery({
  placement,
  dispatchAffordance,
}: {
  placement: Extract<
    CheckoutPlacementProjection,
    { state: "external_outcome_unknown" }
  >;
  dispatchAffordance: RouteDeckSurfaceComponentProps["dispatchAffordance"];
}) {
  if (placement.order_ref === undefined) {
    return (
      <section aria-labelledby="unknown-order-title">
        <h2 id="unknown-order-title">Order confirmation pending</h2>
        <RouteDeckError
          code="external_outcome_unknown"
          message={placement.message}
          correlationId={placement.correlation_id}
        />
        <p>
          Automatic status checks are unavailable because this session has no
          verified order reference.
        </p>
        <p>Keep the reference above for support, and do not place the order again.</p>
      </section>
    );
  }
  return (
    <ReconcilableOrderRecovery
      placement={{ ...placement, order_ref: placement.order_ref }}
      dispatchAffordance={dispatchAffordance}
    />
  );
}

function ReconcilableOrderRecovery({
  placement,
  dispatchAffordance,
}: {
  placement: Extract<
    CheckoutPlacementProjection,
    { state: "external_outcome_unknown" }
  > & { order_ref: string };
  dispatchAffordance: RouteDeckSurfaceComponentProps["dispatchAffordance"];
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const reconcile = useCallback(() => {
    if (pending) return;
    setPending(true);
    setError(null);
    void dispatchAffordance(
      "reconcile_order",
      { order_ref: placement.order_ref },
    )
      .catch((caught: unknown) => {
        setError(
          caught instanceof Error
            ? caught
            : new Error("RouteDeck could not reconcile this order."),
        );
      })
      .finally(() => setPending(false));
  }, [dispatchAffordance, pending, placement.order_ref]);
  return (
    <section aria-labelledby="unknown-order-title">
      <h2 id="unknown-order-title">Order confirmation pending</h2>
      <RouteDeckError
        code="external_outcome_unknown"
        message={placement.message}
        correlationId={placement.correlation_id}
      />
      {error === null ? null : (
        <RouteDeckError code="order_reconciliation_failed" message={error.message} />
      )}
      <button type="button" disabled={pending} onClick={reconcile}>
        {pending ? "Checking order status…" : "Check order status"}
      </button>
    </section>
  );
}

function decodeCheckoutPlacement(
  props: RouteDeckSurfaceComponentProps["props"],
): CheckoutPlacementProjection {
  const state = checkoutString(props.state, "$.checkout.placement.state");
  if (state === "pending") {
    checkoutExactKeys(props, "$.checkout.placement", [
      "state",
      "review_id",
      "expires_at",
    ]);
    const expiresAt = checkoutString(
      props.expires_at,
      "$.checkout.placement.expires_at",
    );
    if (!Number.isFinite(Date.parse(expiresAt))) {
      checkoutInvalid("$.checkout.placement.expires_at", "must be an ISO date-time");
    }
    return {
      state,
      review_id: checkoutString(
        props.review_id,
        "$.checkout.placement.review_id",
      ),
      expires_at: expiresAt,
    };
  }
  if (state === "external_outcome_unknown") {
    checkoutExactKeys(props, "$.checkout.placement", [
      "state",
      "message",
      "correlation_id",
      "order_ref",
    ]);
    return {
      state,
      message: checkoutString(props.message, "$.checkout.placement.message"),
      correlation_id: checkoutString(
        props.correlation_id,
        "$.checkout.placement.correlation_id",
      ),
      ...(props.order_ref === undefined
        ? {}
        : {
            order_ref: checkoutString(
              props.order_ref,
              "$.checkout.placement.order_ref",
            ),
          }),
    };
  }
  checkoutInvalid("$.checkout.placement.state", "is invalid");
}
