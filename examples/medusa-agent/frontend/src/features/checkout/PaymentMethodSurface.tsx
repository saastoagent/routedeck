import { useCallback, useState } from "react";
import {
  RouteDeckError,
  type RouteDeckSurfaceComponentProps,
} from "@routedeck/react";
import {
  RouteDeckStateError,
  type JsonValue,
} from "@routedeck/core";

type PaymentState = "ready" | "missing" | "refresh_failed";

interface PaymentProviderProjection {
  payment_provider_ref: string;
  label: string;
}

interface PaymentProjection {
  state: PaymentState;
  providers: PaymentProviderProjection[];
  message?: string;
}

export function PaymentMethodSurface({
  props,
  dispatchAffordance,
}: RouteDeckSurfaceComponentProps) {
  const projection = decodePaymentProjection(props);
  const [pendingHandle, setPendingHandle] = useState<string | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const selectPayment = useCallback(
    async (paymentProviderRef: string) => {
      if (pendingHandle !== null) return;
      setPendingHandle(paymentProviderRef);
      setError(null);
      try {
        await dispatchAffordance("select_payment", {
          payment_provider_ref: paymentProviderRef,
        });
      } catch (caught) {
        setError(
          caught instanceof Error
            ? caught
            : new Error("RouteDeck could not initialize this payment method."),
        );
      } finally {
        setPendingHandle(null);
      }
    },
    [dispatchAffordance, pendingHandle],
  );

  if (projection.state !== "ready") {
    return (
      <RouteDeckError
        code="payment_method_unavailable"
        message={projection.message}
      />
    );
  }

  return (
    <section aria-labelledby="payment-method-title">
      <h1 id="payment-method-title">Payment method</h1>
      <p>
        This checkout uses the configured system/manual demo payment method. It
        never collects card details.
      </p>
      <div aria-busy={pendingHandle !== null}>
        {projection.providers.map((provider) => (
          <PaymentProviderButton
            key={provider.payment_provider_ref}
            provider={provider}
            pending={pendingHandle === provider.payment_provider_ref}
            disabled={pendingHandle !== null}
            onSelect={selectPayment}
          />
        ))}
      </div>
      {error === null ? null : (
        <RouteDeckError code="payment_selection_failed" message={error.message} />
      )}
    </section>
  );
}

function PaymentProviderButton({
  provider,
  pending,
  disabled,
  onSelect,
}: {
  provider: PaymentProviderProjection;
  pending: boolean;
  disabled: boolean;
  onSelect(paymentProviderRef: string): Promise<void>;
}) {
  const select = useCallback(
    () => void onSelect(provider.payment_provider_ref),
    [onSelect, provider.payment_provider_ref],
  );
  return (
    <button type="button" disabled={disabled} onClick={select}>
      {provider.label}
      {pending ? " — Initializing…" : ""}
    </button>
  );
}

function decodePaymentProjection(
  props: RouteDeckSurfaceComponentProps["props"],
): PaymentProjection {
  checkoutExactKeys(props, "$.checkout.payment_method", [
    "state",
    "providers",
    "message",
  ]);
  const state = checkoutString(props.state, "$.checkout.payment_method.state");
  if (state !== "ready" && state !== "missing" && state !== "refresh_failed") {
    checkoutInvalid("$.checkout.payment_method.state", "is invalid");
  }
  if (!Array.isArray(props.providers)) {
    checkoutInvalid("$.checkout.payment_method.providers", "must be an array");
  }
  const providers = props.providers.map((value, index) => {
    const path = `$.checkout.payment_method.providers[${index}]`;
    const provider = checkoutRecord(value, path);
    checkoutExactKeys(provider, path, ["payment_provider_ref", "label"]);
    return {
      payment_provider_ref: checkoutString(
        provider.payment_provider_ref,
        `${path}.payment_provider_ref`,
      ),
      label: checkoutString(provider.label, `${path}.label`),
    };
  });
  const message =
    props.message === undefined
      ? undefined
      : checkoutString(props.message, "$.checkout.payment_method.message");
  if (state === "ready" && (providers.length !== 1 || message !== undefined)) {
    checkoutInvalid(
      "$.checkout.payment_method",
      "ready state requires exactly one configured provider and no message",
    );
  }
  if (state !== "ready" && (providers.length > 0 || message === undefined)) {
    checkoutInvalid(
      "$.checkout.payment_method",
      "unavailable state requires one message and no providers",
    );
  }
  return {
    state,
    providers,
    ...(message === undefined ? {} : { message }),
  };
}

export function checkoutRecord(
  value: JsonValue | undefined,
  path: string,
): Record<string, JsonValue> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    checkoutInvalid(path, "must be an object");
  }
  return value as Record<string, JsonValue>;
}

export function checkoutExactKeys(
  value: Readonly<Record<string, JsonValue>>,
  path: string,
  allowed: readonly string[],
): void {
  const allowlist = new Set(allowed);
  const extra = Object.keys(value).find((key) => !allowlist.has(key));
  if (extra !== undefined) checkoutInvalid(path, `contains undeclared field ${extra}`);
}

export function checkoutString(
  value: JsonValue | undefined,
  path: string,
): string {
  if (typeof value !== "string" || value.length === 0) {
    checkoutInvalid(path, "must be a non-empty string");
  }
  return value;
}

export function checkoutInteger(
  value: JsonValue | undefined,
  path: string,
  minimum?: number,
): number {
  if (
    typeof value !== "number" ||
    !Number.isInteger(value) ||
    (minimum !== undefined && value < minimum)
  ) {
    checkoutInvalid(path, "must be a valid integer");
  }
  return value;
}

export function checkoutBoolean(
  value: JsonValue | undefined,
  path: string,
): boolean {
  if (typeof value !== "boolean") checkoutInvalid(path, "must be a boolean");
  return value;
}

export function checkoutFormatMoney(amount: number, currencyCode: string): string {
  return `${currencyCode.toUpperCase()} ${new Intl.NumberFormat().format(amount)}`;
}

export function checkoutInvalid(path: string, message: string): never {
  throw new RouteDeckStateError(
    "checkout_projection_invalid",
    `Checkout projection ${path} ${message}.`,
  );
}
