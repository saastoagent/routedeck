import { useCallback, useRef, useState } from "react";
import {
  RouteDeckError,
  type RouteDeckSurfaceComponentProps,
} from "@routedeck/react";

import {
  CartLineItem,
  cartExactKeys,
  cartInteger,
  cartInvalid,
  cartString,
  decodeCartLineItem,
  formatCartMoney,
  type CartLineItemProjection,
} from "./CartLineItem";
import { CartAffordanceId } from "./affordances";
import { CheckoutAffordanceId } from "../checkout/affordances";

interface CartSummaryProjection {
  cart_ref: string;
  currency_code: string;
  items: CartLineItemProjection[];
  subtotal: number;
  shipping_total: number;
  tax_total: number;
  discount_total: number;
  total: number;
}

export function CartSummarySurface({
  props,
  dispatchAffordance,
}: RouteDeckSurfaceComponentProps) {
  const cart = decodeCartSummary(props);
  const checkoutInFlight = useRef(false);
  const [checkoutPending, setCheckoutPending] = useState(false);
  const [checkoutError, setCheckoutError] = useState<Error | null>(null);
  const updateItem = useCallback(
    async (lineItemRef: string, quantity: number) => {
      await dispatchAffordance(CartAffordanceId.UpdateItem, {
        line_item_ref: lineItemRef,
        quantity,
      });
    },
    [dispatchAffordance],
  );
  const removeItem = useCallback(
    async (lineItemRef: string) => {
      await dispatchAffordance(CartAffordanceId.RemoveItem, {
        line_item_ref: lineItemRef,
      });
    },
    [dispatchAffordance],
  );
  const startCheckout = useCallback(async () => {
    if (checkoutInFlight.current) return;
    checkoutInFlight.current = true;
    setCheckoutPending(true);
    setCheckoutError(null);
    try {
      await dispatchAffordance(CheckoutAffordanceId.Start);
    } catch (caught) {
      setCheckoutError(
        caught instanceof Error
          ? caught
          : new Error("RouteDeck could not start checkout."),
      );
    } finally {
      checkoutInFlight.current = false;
      setCheckoutPending(false);
    }
  }, [dispatchAffordance]);

  return (
    <section data-cart-summary={cart.cart_ref} aria-labelledby="cart-summary-title">
      <header>
        <h1 id="cart-summary-title">Your cart</h1>
        <p>
          {cart.items.length} {cart.items.length === 1 ? "line item" : "line items"}
        </p>
      </header>

      {cart.items.length === 0 ? (
        <p>Your cart is empty.</p>
      ) : (
        <ul>
          {cart.items.map((line) => (
            <CartLineItem
              key={line.line_item_ref}
              line={line}
              currencyCode={cart.currency_code}
              onUpdate={updateItem}
              onRemove={removeItem}
            />
          ))}
        </ul>
      )}

      <dl aria-label="Cart totals">
        <div>
          <dt>Subtotal</dt>
          <dd>{formatCartMoney(cart.subtotal, cart.currency_code)}</dd>
        </div>
        <div>
          <dt>Shipping</dt>
          <dd>{formatCartMoney(cart.shipping_total, cart.currency_code)}</dd>
        </div>
        <div>
          <dt>Tax</dt>
          <dd>{formatCartMoney(cart.tax_total, cart.currency_code)}</dd>
        </div>
        <div>
          <dt>Discount</dt>
          <dd>{formatCartMoney(cart.discount_total, cart.currency_code)}</dd>
        </div>
        <div>
          <dt>Total</dt>
          <dd>
            <strong>{formatCartMoney(cart.total, cart.currency_code)}</strong>
          </dd>
        </div>
      </dl>
      {cart.items.length === 0 ? null : (
        <div aria-busy={checkoutPending}>
          {checkoutError === null ? null : (
            <RouteDeckError
              code="checkout_start_failed"
              message={checkoutError.message}
            />
          )}
          <button
            type="button"
            disabled={checkoutPending}
            onClick={() => void startCheckout()}
          >
            {checkoutPending ? "Starting checkout…" : "Checkout"}
          </button>
        </div>
      )}
    </section>
  );
}

export function decodeCartSummary(
  props: RouteDeckSurfaceComponentProps["props"],
): CartSummaryProjection {
  cartExactKeys(props, "$.cart.summary", [
    "cart_ref",
    "currency_code",
    "items",
    "subtotal",
    "shipping_total",
    "tax_total",
    "discount_total",
    "total",
  ]);
  if (!Array.isArray(props.items)) {
    cartInvalid("$.cart.summary.items", "must be an array");
  }
  const items = props.items.map((item, index) =>
    decodeCartLineItem(item, `$.cart.summary.items[${index}]`),
  );
  const lineRefs = items.map((item) => item.line_item_ref);
  if (new Set(lineRefs).size !== lineRefs.length) {
    cartInvalid("$.cart.summary.items", "contains duplicate line-item handles");
  }
  const currencyCode = cartString(
    props.currency_code,
    "$.cart.summary.currency_code",
  );
  if (currencyCode.length !== 3) {
    cartInvalid("$.cart.summary.currency_code", "must have length 3");
  }
  return {
    cart_ref: cartString(props.cart_ref, "$.cart.summary.cart_ref"),
    currency_code: currencyCode,
    items,
    subtotal: cartInteger(props.subtotal, "$.cart.summary.subtotal"),
    shipping_total: cartInteger(
      props.shipping_total,
      "$.cart.summary.shipping_total",
    ),
    tax_total: cartInteger(props.tax_total, "$.cart.summary.tax_total"),
    discount_total: cartInteger(
      props.discount_total,
      "$.cart.summary.discount_total",
    ),
    total: cartInteger(props.total, "$.cart.summary.total"),
  };
}
