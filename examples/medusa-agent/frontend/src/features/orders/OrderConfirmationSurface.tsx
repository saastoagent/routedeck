import { useCallback, useState } from "react";
import {
  RouteDeckError,
  type RouteDeckSurfaceComponentProps,
} from "@routedeck/react";
import type { JsonValue } from "@routedeck/core";

import {
  checkoutExactKeys,
  checkoutFormatMoney,
  checkoutInteger,
  checkoutInvalid,
  checkoutRecord,
  checkoutString,
} from "../checkout/PaymentMethodSurface";

interface ConfirmedOrderLine {
  title: string;
  variant_title?: string;
  quantity: number;
  unit_amount: number;
  total: number;
}

interface VerifiedOrderProjection {
  confirmation_handle: string;
  display_id: string;
  status: string;
  currency_code: string;
  items: ConfirmedOrderLine[];
  subtotal: number;
  shipping_total: number;
  tax_total: number;
  discount_total: number;
  total: number;
  shipping_label: string;
  payment_label: string;
}

export function OrderConfirmationSurface({
  props,
  dispatchAffordance,
}: RouteDeckSurfaceComponentProps) {
  const order = decodeVerifiedOrder(props);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const continueShopping = useCallback(() => {
    if (pending) return;
    setPending(true);
    setError(null);
    void dispatchAffordance("continue_shopping")
      .catch((caught: unknown) => {
        setError(
          caught instanceof Error
            ? caught
            : new Error("RouteDeck could not return to the catalog."),
        );
      })
      .finally(() => setPending(false));
  }, [dispatchAffordance, pending]);

  return (
    <section
      aria-labelledby="order-confirmation-title"
      data-confirmation={order.confirmation_handle}
    >
      <h1 id="order-confirmation-title">Order confirmed</h1>
      <p>Order {order.display_id}</p>
      <p>Status: {order.status}</p>
      <ul>
        {order.items.map((item, index) => (
          <li key={`${item.title}:${index}`}>
            <span>{item.title}</span>
            {item.variant_title === undefined ? null : (
              <span>{item.variant_title}</span>
            )}
            <span>Quantity {item.quantity}</span>
            <span>{checkoutFormatMoney(item.total, order.currency_code)}</span>
          </li>
        ))}
      </ul>
      <dl aria-label="Confirmed order totals">
        <OrderTotal label="Subtotal" value={order.subtotal} currency={order.currency_code} />
        <OrderTotal label="Shipping" value={order.shipping_total} currency={order.currency_code} />
        <OrderTotal label="Tax" value={order.tax_total} currency={order.currency_code} />
        <OrderTotal label="Discount" value={order.discount_total} currency={order.currency_code} />
        <OrderTotal label="Total" value={order.total} currency={order.currency_code} />
      </dl>
      <p>Delivery: {order.shipping_label}</p>
      <p>Payment: {order.payment_label}</p>
      {error === null ? null : (
        <RouteDeckError code="continue_shopping_failed" message={error.message} />
      )}
      <button type="button" disabled={pending} onClick={continueShopping}>
        {pending ? "Returning to products…" : "Continue shopping"}
      </button>
    </section>
  );
}

function OrderTotal({
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

function decodeVerifiedOrder(
  props: RouteDeckSurfaceComponentProps["props"],
): VerifiedOrderProjection {
  checkoutExactKeys(props, "$.orders.confirmation", [
    "confirmation_handle",
    "display_id",
    "status",
    "currency_code",
    "items",
    "subtotal",
    "shipping_total",
    "tax_total",
    "discount_total",
    "total",
    "shipping_label",
    "payment_label",
  ]);
  if (!Array.isArray(props.items) || props.items.length === 0) {
    checkoutInvalid("$.orders.confirmation.items", "must contain verified items");
  }
  const currencyCode = checkoutString(
    props.currency_code,
    "$.orders.confirmation.currency_code",
  );
  if (currencyCode.length !== 3) {
    checkoutInvalid("$.orders.confirmation.currency_code", "must have length 3");
  }
  return {
    confirmation_handle: checkoutString(
      props.confirmation_handle,
      "$.orders.confirmation.confirmation_handle",
    ),
    display_id: checkoutString(
      props.display_id,
      "$.orders.confirmation.display_id",
    ),
    status: checkoutString(props.status, "$.orders.confirmation.status"),
    currency_code: currencyCode,
    items: props.items.map((item, index) => decodeOrderLine(item, index)),
    subtotal: checkoutInteger(props.subtotal, "$.orders.confirmation.subtotal"),
    shipping_total: checkoutInteger(
      props.shipping_total,
      "$.orders.confirmation.shipping_total",
    ),
    tax_total: checkoutInteger(props.tax_total, "$.orders.confirmation.tax_total"),
    discount_total: checkoutInteger(
      props.discount_total,
      "$.orders.confirmation.discount_total",
    ),
    total: checkoutInteger(props.total, "$.orders.confirmation.total"),
    shipping_label: checkoutString(
      props.shipping_label,
      "$.orders.confirmation.shipping_label",
    ),
    payment_label: checkoutString(
      props.payment_label,
      "$.orders.confirmation.payment_label",
    ),
  };
}

function decodeOrderLine(value: JsonValue, index: number): ConfirmedOrderLine {
  const path = `$.orders.confirmation.items[${index}]`;
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
