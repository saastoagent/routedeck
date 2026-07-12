import {
  useCallback,
  useId,
  useState,
  type ChangeEvent,
  type FormEvent,
} from "react";
import { RouteDeckError } from "@routedeck/react";

import type { CatalogVariantProjection } from "./VariantSelector";

export interface AddToCartAffordanceProps {
  selectedVariant?: CatalogVariantProjection;
  onAdd(variantHandle: string, quantity: number): Promise<void>;
}

type QuantityValue = number | "";

export function AddToCartAffordance({
  selectedVariant,
  onAdd,
}: AddToCartAffordanceProps) {
  const quantityId = useId();
  const guidanceId = useId();
  const [quantity, setQuantity] = useState<QuantityValue>(1);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const selectedVariantIsInStock =
    selectedVariant?.inventory_status === "in_stock";
  const quantityIsValid =
    typeof quantity === "number" &&
    Number.isInteger(quantity) &&
    quantity > 0;

  const updateQuantity = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    const nextQuantity = event.currentTarget.valueAsNumber;
    setQuantity(Number.isNaN(nextQuantity) ? "" : nextQuantity);
  }, []);

  const submit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (pending) return;
      if (selectedVariant?.inventory_status !== "in_stock") {
        setError(new Error("Select an in-stock variant before adding it."));
        return;
      }
      if (!quantityIsValid) {
        setError(new Error("Quantity must be a positive whole number."));
        return;
      }

      setPending(true);
      setError(null);
      try {
        await onAdd(selectedVariant.interaction_handle, quantity);
      } catch (caught) {
        setError(
          caught instanceof Error
            ? caught
            : new Error("RouteDeck could not add this item to the cart."),
        );
      } finally {
        setPending(false);
      }
    },
    [onAdd, pending, quantity, quantityIsValid, selectedVariant],
  );

  return (
    <form
      data-catalog-add-to-cart=""
      aria-busy={pending}
      onSubmit={(event) => void submit(event)}
    >
      <label htmlFor={quantityId}>Quantity</label>
      <input
        id={quantityId}
        name="quantity"
        type="number"
        inputMode="numeric"
        min={1}
        step={1}
        required
        value={quantity}
        disabled={!selectedVariantIsInStock || pending}
        aria-describedby={guidanceId}
        onChange={updateQuantity}
      />
      <button
        type="submit"
        disabled={!selectedVariantIsInStock || !quantityIsValid || pending}
      >
        {pending ? "Adding..." : "Add to cart"}
      </button>
      <p id={guidanceId} aria-live="polite">
        {addGuidance(selectedVariant, pending)}
      </p>
      {error === null ? null : (
        <RouteDeckError code="catalog_add_item_failed" message={error.message} />
      )}
    </form>
  );
}

function addGuidance(
  selectedVariant: CatalogVariantProjection | undefined,
  pending: boolean,
): string {
  if (pending) return "Adding the selected variant to your cart.";
  if (selectedVariant === undefined) {
    return "Choose an in-stock variant to continue.";
  }
  if (selectedVariant.inventory_status !== "in_stock") {
    return "The selected variant is not confirmed in stock.";
  }
  return `${selectedVariant.title} is selected and ready to add.`;
}
