import { useCallback, useState } from "react";
import type { JsonValue } from "@routedeck/core";
import { RouteDeckError } from "@routedeck/react";

import {
  catalogExactKeys,
  catalogInteger,
  catalogInvalid,
  catalogRecord,
  catalogString,
  catalogStringArray,
  decodeCatalogPrice,
  formatCatalogPrice,
  type CatalogPriceProjection,
} from "./ProductCard";

export type CatalogInventoryStatus = "in_stock" | "out_of_stock" | "unknown";

export interface CatalogVariantProjection {
  interaction_handle: string;
  title: string;
  sku?: string;
  price: CatalogPriceProjection;
  inventory_status: CatalogInventoryStatus;
  inventory_quantity?: number;
  option_values: string[];
}

export interface VariantSelectorProps {
  variants: readonly CatalogVariantProjection[];
  selectedVariantHandle?: string;
  onSelect(interactionHandle: string): Promise<void>;
}

export function VariantSelector({
  variants,
  selectedVariantHandle,
  onSelect,
}: VariantSelectorProps) {
  const [pendingHandle, setPendingHandle] = useState<string | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const select = useCallback(
    async (interactionHandle: string) => {
      if (pendingHandle !== null) return;
      setPendingHandle(interactionHandle);
      setError(null);
      try {
        await onSelect(interactionHandle);
      } catch (caught) {
        setError(
          caught instanceof Error
            ? caught
            : new Error("RouteDeck could not select this variant."),
        );
      } finally {
        setPendingHandle(null);
      }
    },
    [onSelect, pendingHandle],
  );

  return (
    <fieldset aria-busy={pendingHandle !== null}>
      <legend>Choose a variant</legend>
      {variants.map((variant) => (
        <VariantChoice
          key={variant.interaction_handle}
          variant={variant}
          selected={selectedVariantHandle === variant.interaction_handle}
          pending={pendingHandle === variant.interaction_handle}
          disabled={
            pendingHandle !== null || variant.inventory_status === "out_of_stock"
          }
          onSelect={select}
        />
      ))}
      {error === null ? null : (
        <RouteDeckError code="catalog_variant_failed" message={error.message} />
      )}
    </fieldset>
  );
}

function VariantChoice({
  variant,
  selected,
  pending,
  disabled,
  onSelect,
}: {
  variant: CatalogVariantProjection;
  selected: boolean;
  pending: boolean;
  disabled: boolean;
  onSelect(interactionHandle: string): Promise<void>;
}) {
  const select = useCallback(
    () => void onSelect(variant.interaction_handle),
    [onSelect, variant.interaction_handle],
  );
  const optionLabel =
    variant.option_values.length === 0
      ? variant.title
      : `${variant.title} — ${variant.option_values.join(" / ")}`;
  return (
    <label>
      <input
        type="radio"
        name="catalog-variant"
        value={variant.interaction_handle}
        checked={selected}
        disabled={disabled}
        onChange={select}
      />
      <span>{optionLabel}</span>
      <span>{formatCatalogPrice(variant.price)}</span>
      {pending ? <span> Selecting…</span> : null}
      {variant.inventory_status === "out_of_stock" ? (
        <span> Out of stock</span>
      ) : null}
    </label>
  );
}

export function decodeCatalogVariant(
  value: JsonValue | undefined,
  path: string,
): CatalogVariantProjection {
  const record = catalogRecord(value, path);
  catalogExactKeys(record, path, [
    "interaction_handle",
    "title",
    "sku",
    "price",
    "inventory_status",
    "inventory_quantity",
    "option_values",
  ]);
  const inventoryStatus = catalogString(
    record.inventory_status,
    `${path}.inventory_status`,
  );
  if (
    inventoryStatus !== "in_stock" &&
    inventoryStatus !== "out_of_stock" &&
    inventoryStatus !== "unknown"
  ) {
    catalogInvalid(`${path}.inventory_status`, "is not declared");
  }
  return {
    interaction_handle: catalogString(
      record.interaction_handle,
      `${path}.interaction_handle`,
    ),
    title: catalogString(record.title, `${path}.title`),
    ...(record.sku === undefined
      ? {}
      : { sku: catalogString(record.sku, `${path}.sku`) }),
    price: decodeCatalogPrice(record.price, `${path}.price`),
    inventory_status: inventoryStatus,
    ...(record.inventory_quantity === undefined
      ? {}
      : {
          inventory_quantity: catalogInteger(
            record.inventory_quantity,
            `${path}.inventory_quantity`,
          ),
        }),
    option_values: catalogStringArray(
      record.option_values,
      `${path}.option_values`,
    ),
  };
}
