import { useCallback, useState } from "react";
import {
  RouteDeckError,
  type RouteDeckSurfaceComponentProps,
} from "@routedeck/react";
import type { JsonValue } from "@routedeck/core";

import {
  CheckoutReviewAuthorityStatus,
  useCheckoutReviewAuthority,
} from "./CheckoutReviewAuthority";
import { CheckoutAffordanceId } from "./affordances";

import {
  checkoutBoolean,
  checkoutExactKeys,
  checkoutFormatMoney,
  checkoutInteger,
  checkoutInvalid,
  checkoutRecord,
  checkoutString,
} from "./PaymentMethodSurface";

interface ReviewLineProjection {
  title: string;
  variant_title?: string;
  quantity: number;
  unit_amount: number;
  total: number;
}

interface OrderReviewProjection {
  form_handle: string;
  items: ReviewLineProjection[];
  currency_code: string;
  subtotal: number;
  shipping_total: number;
  tax_total: number;
  discount_total: number;
  total: number;
  shipping_label: string;
  payment_label: string;
  contact_complete: boolean;
  billing_complete: boolean;
}

export function OrderReviewSurface({
  props,
  dispatchAffordance,
}: RouteDeckSurfaceComponentProps) {
  const review = decodeOrderReview(props);
  const authority = useCheckoutReviewAuthority();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const proposeOrder = useCallback(() => {
    if (pending || authority.state !== "ready") return;
    setPending(true);
    setError(null);
    void dispatchAffordance(CheckoutAffordanceId.ProposeOrder)
      .catch((caught: unknown) => {
        setError(
          caught instanceof Error
            ? caught
            : new Error("RouteDeck could not prepare this order review."),
        );
      })
      .finally(() => setPending(false));
  }, [authority.state, dispatchAffordance, pending]);

  return (
    <section aria-labelledby="order-review-title">
      <h1 id="order-review-title">Review your order</h1>
      <ul>
        {review.items.map((item, index) => (
          <li key={`${item.title}:${index}`}>
            <span>{item.title}</span>
            {item.variant_title === undefined ? null : (
              <span>{item.variant_title}</span>
            )}
            <span>Quantity {item.quantity}</span>
            <span>{checkoutFormatMoney(item.total, review.currency_code)}</span>
          </li>
        ))}
      </ul>
      <dl aria-label="Order totals">
        <ReviewTotal label="Subtotal" value={review.subtotal} currency={review.currency_code} />
        <ReviewTotal label="Shipping" value={review.shipping_total} currency={review.currency_code} />
        <ReviewTotal label="Tax" value={review.tax_total} currency={review.currency_code} />
        <ReviewTotal label="Discount" value={review.discount_total} currency={review.currency_code} />
        <ReviewTotal label="Total" value={review.total} currency={review.currency_code} />
      </dl>
      <p>Delivery: {review.shipping_label}</p>
      <p>Payment: {review.payment_label}</p>
      <p>
        Contact {review.contact_complete ? "complete" : "incomplete"}; billing{" "}
        {review.billing_complete ? "complete" : "incomplete"}.
      </p>
      <CheckoutReviewAuthorityStatus authority={authority} />
      {error === null ? null : (
        <RouteDeckError code="order_proposal_failed" message={error.message} />
      )}
      <button
        type="button"
        disabled={pending || authority.state !== "ready"}
        onClick={proposeOrder}
      >
        {pending ? "Preparing review…" : "Review and place order"}
      </button>
    </section>
  );
}

function ReviewTotal({
  label,
  value,
  currency,
}: {
  label: string;
  value: number;
  currency: string;
}) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{checkoutFormatMoney(value, currency)}</dd>
    </div>
  );
}

export function decodeOrderReview(
  props: RouteDeckSurfaceComponentProps["props"],
): OrderReviewProjection {
  checkoutExactKeys(props, "$.checkout.order_review", [
    "form_handle",
    "items",
    "currency_code",
    "subtotal",
    "shipping_total",
    "tax_total",
    "discount_total",
    "total",
    "shipping_label",
    "payment_label",
    "contact_complete",
    "billing_complete",
  ]);
  if (!Array.isArray(props.items) || props.items.length === 0) {
    checkoutInvalid("$.checkout.order_review.items", "must contain order items");
  }
  const currencyCode = checkoutString(
    props.currency_code,
    "$.checkout.order_review.currency_code",
  );
  if (currencyCode.length !== 3) {
    checkoutInvalid("$.checkout.order_review.currency_code", "must have length 3");
  }
  return {
    form_handle: checkoutString(
      props.form_handle,
      "$.checkout.order_review.form_handle",
    ),
    items: props.items.map((value, index) => decodeReviewLine(value, index)),
    currency_code: currencyCode,
    subtotal: checkoutInteger(props.subtotal, "$.checkout.order_review.subtotal"),
    shipping_total: checkoutInteger(
      props.shipping_total,
      "$.checkout.order_review.shipping_total",
    ),
    tax_total: checkoutInteger(props.tax_total, "$.checkout.order_review.tax_total"),
    discount_total: checkoutInteger(
      props.discount_total,
      "$.checkout.order_review.discount_total",
    ),
    total: checkoutInteger(props.total, "$.checkout.order_review.total"),
    shipping_label: checkoutString(
      props.shipping_label,
      "$.checkout.order_review.shipping_label",
    ),
    payment_label: checkoutString(
      props.payment_label,
      "$.checkout.order_review.payment_label",
    ),
    contact_complete: checkoutBoolean(
      props.contact_complete,
      "$.checkout.order_review.contact_complete",
    ),
    billing_complete: checkoutBoolean(
      props.billing_complete,
      "$.checkout.order_review.billing_complete",
    ),
  };
}

function decodeReviewLine(value: JsonValue, index: number): ReviewLineProjection {
  const path = `$.checkout.order_review.items[${index}]`;
  const line = checkoutRecord(value, path);
  checkoutExactKeys(line, path, [
    "title",
    "variant_title",
    "quantity",
    "unit_amount",
    "total",
  ]);
  return {
    title: checkoutString(line.title, `${path}.title`),
    ...(line.variant_title === undefined
      ? {}
      : {
          variant_title: checkoutString(
            line.variant_title,
            `${path}.variant_title`,
          ),
        }),
    quantity: checkoutInteger(line.quantity, `${path}.quantity`, 1),
    unit_amount: checkoutInteger(line.unit_amount, `${path}.unit_amount`),
    total: checkoutInteger(line.total, `${path}.total`),
  };
}
