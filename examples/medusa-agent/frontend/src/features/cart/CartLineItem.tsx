import { useCallback, useState } from "react";
import {
  RouteDeckStateError,
  type JsonValue,
} from "@routedeck/core";
import { RouteDeckError } from "@routedeck/react";

export interface CartLineItemProjection {
  line_item_ref: string;
  title: string;
  product_title?: string;
  variant_title?: string;
  selected_options: string[];
  quantity: number;
  unit_price: number;
  line_total?: number;
}

export interface CartLineItemProps {
  line: CartLineItemProjection;
  currencyCode: string;
  onUpdate(lineItemRef: string, quantity: number): Promise<void>;
  onRemove(lineItemRef: string): Promise<void>;
}

type PendingAction = "decrease" | "increase" | "remove";

const cartNumberFormatter = new Intl.NumberFormat();

export function CartLineItem({
  line,
  currencyCode,
  onUpdate,
  onRemove,
}: CartLineItemProps) {
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
  const [error, setError] = useState<Error | null>(null);

  const updateQuantity = useCallback(
    async (quantity: number, action: Exclude<PendingAction, "remove">) => {
      if (pendingAction !== null) return;
      setPendingAction(action);
      setError(null);
      try {
        await onUpdate(line.line_item_ref, quantity);
      } catch (caught) {
        setError(
          caught instanceof Error
            ? caught
            : new Error("RouteDeck could not update this cart item."),
        );
      } finally {
        setPendingAction(null);
      }
    },
    [line.line_item_ref, onUpdate, pendingAction],
  );

  const decrease = useCallback(() => {
    if (line.quantity <= 1) return;
    void updateQuantity(line.quantity - 1, "decrease");
  }, [line.quantity, updateQuantity]);

  const increase = useCallback(() => {
    void updateQuantity(line.quantity + 1, "increase");
  }, [line.quantity, updateQuantity]);

  const remove = useCallback(async () => {
    if (pendingAction !== null) return;
    setPendingAction("remove");
    setError(null);
    try {
      await onRemove(line.line_item_ref);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught
          : new Error("RouteDeck could not remove this cart item."),
      );
    } finally {
      setPendingAction(null);
    }
  }, [line.line_item_ref, onRemove, pendingAction]);

  return (
    <li data-cart-line={line.line_item_ref} aria-busy={pendingAction !== null}>
      <article>
        <header>
          <h2>{line.title}</h2>
          {line.product_title === undefined ? null : <p>{line.product_title}</p>}
          {line.variant_title === undefined ? null : <p>{line.variant_title}</p>}
        </header>

        {line.selected_options.length === 0 ? null : (
          <dl aria-label="Selected options">
            <div>
              <dt>Options</dt>
              <dd>{line.selected_options.join(" / ")}</dd>
            </div>
          </dl>
        )}

        <p>
          Unit price: {formatCartMoney(line.unit_price, currencyCode)}
        </p>
        {line.line_total === undefined ? null : (
          <p>Line total: {formatCartMoney(line.line_total, currencyCode)}</p>
        )}

        <div role="group" aria-label={`Quantity for ${line.title}`}>
          <button
            type="button"
            onClick={decrease}
            disabled={pendingAction !== null || line.quantity <= 1}
            aria-label={`Decrease quantity of ${line.title}`}
          >
            -
          </button>
          <output aria-live="polite">{line.quantity}</output>
          <button
            type="button"
            onClick={increase}
            disabled={pendingAction !== null}
            aria-label={`Increase quantity of ${line.title}`}
          >
            +
          </button>
        </div>

        <button
          type="button"
          onClick={() => void remove()}
          disabled={pendingAction !== null}
        >
          {pendingAction === "remove" ? "Removing..." : "Remove"}
        </button>

        {error === null ? null : (
          <RouteDeckError code="cart_line_action_failed" message={error.message} />
        )}
      </article>
    </li>
  );
}

export function decodeCartLineItem(
  value: JsonValue | undefined,
  path: string,
): CartLineItemProjection {
  const line = cartRecord(value, path);
  cartExactKeys(line, path, [
    "line_item_ref",
    "title",
    "product_title",
    "variant_title",
    "selected_options",
    "quantity",
    "unit_price",
    "line_total",
  ]);
  return {
    line_item_ref: cartString(line.line_item_ref, `${path}.line_item_ref`),
    title: cartString(line.title, `${path}.title`),
    ...(line.product_title === undefined
      ? {}
      : {
          product_title: cartString(
            line.product_title,
            `${path}.product_title`,
          ),
        }),
    ...(line.variant_title === undefined
      ? {}
      : {
          variant_title: cartString(
            line.variant_title,
            `${path}.variant_title`,
          ),
        }),
    selected_options: cartStringArray(
      line.selected_options,
      `${path}.selected_options`,
    ),
    quantity: cartInteger(line.quantity, `${path}.quantity`, 1),
    unit_price: cartInteger(line.unit_price, `${path}.unit_price`),
    ...(line.line_total === undefined
      ? {}
      : { line_total: cartInteger(line.line_total, `${path}.line_total`) }),
  };
}

export function formatCartMoney(amount: number, currencyCode: string): string {
  return `${currencyCode.toUpperCase()} ${cartNumberFormatter.format(amount)}`;
}

export function cartRecord(
  value: JsonValue | undefined,
  path: string,
): Record<string, JsonValue> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    cartInvalid(path, "must be an object");
  }
  return value as Record<string, JsonValue>;
}

export function cartString(
  value: JsonValue | undefined,
  path: string,
): string {
  if (typeof value !== "string" || value.length === 0) {
    cartInvalid(path, "must be a non-empty string");
  }
  return value;
}

export function cartInteger(
  value: JsonValue | undefined,
  path: string,
  minimum?: number,
): number {
  if (
    typeof value !== "number" ||
    !Number.isInteger(value) ||
    (minimum !== undefined && value < minimum)
  ) {
    cartInvalid(path, "must be a valid integer");
  }
  return value;
}

export function cartStringArray(
  value: JsonValue | undefined,
  path: string,
): string[] {
  if (!Array.isArray(value)) cartInvalid(path, "must be an array");
  return value.map((item, index) => cartString(item, `${path}[${index}]`));
}

export function cartExactKeys(
  record: Readonly<Record<string, JsonValue>>,
  path: string,
  allowedKeys: readonly string[],
): void {
  const allowed = new Set(allowedKeys);
  const extra = Object.keys(record).find((key) => !allowed.has(key));
  if (extra !== undefined) cartInvalid(path, `contains undeclared field ${extra}`);
}

export function cartInvalid(path: string, message: string): never {
  throw new RouteDeckStateError(
    "cart_projection_invalid",
    `Cart projection ${path} ${message}.`,
  );
}
