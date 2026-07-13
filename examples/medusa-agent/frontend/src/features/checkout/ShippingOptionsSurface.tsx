import { useCallback, useState } from "react";
import {
  RouteDeckError,
  type RouteDeckSurfaceComponentProps,
} from "@routedeck/react";
import {
  RouteDeckStateError,
  type JsonValue,
} from "@routedeck/core";

import { CheckoutAffordanceId } from "./affordances";

type ShippingState = "ready" | "empty" | "refresh_failed";

interface ShippingOptionProjection {
  shipping_option_ref: string;
  label: string;
  amount: number;
  currency_code: string;
}

interface ShippingProjection {
  state: ShippingState;
  options: ShippingOptionProjection[];
  message?: string;
}

export function ShippingOptionsSurface({
  props,
  dispatchAffordance,
}: RouteDeckSurfaceComponentProps) {
  const projection = decodeShippingProjection(props);
  const [pendingHandle, setPendingHandle] = useState<string | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const selectOption = useCallback(
    async (shippingOptionRef: string) => {
      if (pendingHandle !== null) return;
      setPendingHandle(shippingOptionRef);
      setError(null);
      try {
        await dispatchAffordance(CheckoutAffordanceId.SelectShipping, {
          shipping_option_ref: shippingOptionRef,
        });
      } catch (caught) {
        setError(
          caught instanceof Error
            ? caught
            : new Error("RouteDeck could not select this delivery option."),
        );
      } finally {
        setPendingHandle(null);
      }
    },
    [dispatchAffordance, pendingHandle],
  );

  if (projection.state !== "ready") {
    return projection.state === "refresh_failed" ? (
      <RouteDeckError
        code="shipping_options_unavailable"
        message={projection.message}
      />
    ) : (
      <section aria-labelledby="shipping-options-title">
        <h1 id="shipping-options-title">Delivery options</h1>
        <p role="status">{projection.message}</p>
      </section>
    );
  }

  return (
    <section aria-labelledby="shipping-options-title">
      <h1 id="shipping-options-title">Delivery options</h1>
      <div aria-busy={pendingHandle !== null}>
        {projection.options.map((option) => (
          <ShippingOptionButton
            key={option.shipping_option_ref}
            option={option}
            pending={pendingHandle === option.shipping_option_ref}
            disabled={pendingHandle !== null}
            onSelect={selectOption}
          />
        ))}
      </div>
      {error === null ? null : (
        <RouteDeckError code="shipping_selection_failed" message={error.message} />
      )}
    </section>
  );
}

function ShippingOptionButton({
  option,
  pending,
  disabled,
  onSelect,
}: {
  option: ShippingOptionProjection;
  pending: boolean;
  disabled: boolean;
  onSelect(shippingOptionRef: string): Promise<void>;
}) {
  const select = useCallback(
    () => void onSelect(option.shipping_option_ref),
    [onSelect, option.shipping_option_ref],
  );
  return (
    <button type="button" disabled={disabled} onClick={select}>
      <span>{option.label}</span>
      <span>{formatShippingPrice(option)}</span>
      {pending ? <span> Selecting…</span> : null}
    </button>
  );
}

function decodeShippingProjection(
  props: RouteDeckSurfaceComponentProps["props"],
): ShippingProjection {
  exactKeys(props, "$.checkout.shipping_options", [
    "state",
    "options",
    "message",
  ]);
  const state = requiredString(props.state, "$.checkout.shipping_options.state");
  if (state !== "ready" && state !== "empty" && state !== "refresh_failed") {
    invalid("$.checkout.shipping_options.state", "is invalid");
  }
  if (!Array.isArray(props.options)) {
    invalid("$.checkout.shipping_options.options", "must be an array");
  }
  const options = props.options.map((option, index) =>
    decodeShippingOption(
      option,
      `$.checkout.shipping_options.options[${index}]`,
    ),
  );
  const message =
    props.message === undefined
      ? undefined
      : requiredString(props.message, "$.checkout.shipping_options.message");
  if (state === "ready" && (options.length === 0 || message !== undefined)) {
    invalid(
      "$.checkout.shipping_options",
      "ready state requires options and no message",
    );
  }
  if (state !== "ready" && (options.length > 0 || message === undefined)) {
    invalid(
      "$.checkout.shipping_options",
      "unavailable state requires one message and no options",
    );
  }
  return {
    state,
    options,
    ...(message === undefined ? {} : { message }),
  };
}

function decodeShippingOption(
  value: JsonValue | undefined,
  path: string,
): ShippingOptionProjection {
  const option = recordValue(value, path);
  exactKeys(option, path, [
    "shipping_option_ref",
    "label",
    "amount",
    "currency_code",
  ]);
  const currencyCode = requiredString(
    option.currency_code,
    `${path}.currency_code`,
  );
  if (currencyCode.length !== 3) {
    invalid(`${path}.currency_code`, "must have length 3");
  }
  return {
    shipping_option_ref: requiredString(
      option.shipping_option_ref,
      `${path}.shipping_option_ref`,
    ),
    label: requiredString(option.label, `${path}.label`),
    amount: nonnegativeInteger(option.amount, `${path}.amount`),
    currency_code: currencyCode,
  };
}

function formatShippingPrice(option: ShippingOptionProjection): string {
  return `${option.currency_code.toUpperCase()} ${new Intl.NumberFormat().format(option.amount)}`;
}

function recordValue(
  value: JsonValue | undefined,
  path: string,
): Record<string, JsonValue> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    invalid(path, "must be an object");
  }
  return value as Record<string, JsonValue>;
}

function exactKeys(
  value: Readonly<Record<string, JsonValue>>,
  path: string,
  allowed: readonly string[],
): void {
  const allowlist = new Set(allowed);
  const extra = Object.keys(value).find((key) => !allowlist.has(key));
  if (extra !== undefined) invalid(path, `contains undeclared field ${extra}`);
}

function requiredString(value: JsonValue | undefined, path: string): string {
  if (typeof value !== "string" || value.length === 0) {
    invalid(path, "must be a non-empty string");
  }
  return value;
}

function nonnegativeInteger(value: JsonValue | undefined, path: string): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) {
    invalid(path, "must be a nonnegative integer");
  }
  return value;
}

function invalid(path: string, message: string): never {
  throw new RouteDeckStateError(
    "checkout_projection_invalid",
    `Checkout projection ${path} ${message}.`,
  );
}
