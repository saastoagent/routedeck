import { useCallback } from "react";
import type { JsonValue } from "@routedeck/core";
import type { RouteDeckSurfaceComponentProps } from "@routedeck/react";

import {
  catalogExactKeys,
  catalogInvalid,
  catalogRecord,
  catalogString,
  catalogStringArray,
  formatCatalogPrice,
} from "./ProductCard";
import { AddToCartAffordance } from "./AddToCartAffordance";
import { CatalogAffordanceId } from "./affordances";
import {
  VariantSelector,
  decodeCatalogVariant,
  type CatalogVariantProjection,
} from "./VariantSelector";

interface CatalogOptionProjection {
  title: string;
  values: string[];
}

interface CatalogProductDetailProjection {
  interaction_handle: string;
  product_handle: string;
  title: string;
  description?: string;
  thumbnail_url?: string;
  image_urls: string[];
  options: CatalogOptionProjection[];
  variants: CatalogVariantProjection[];
  selected_variant_handle?: string;
}

export function ProductDetailSurface({
  props,
  dispatchAffordance,
}: RouteDeckSurfaceComponentProps) {
  const product = decodeProductDetail(props);
  const selectVariant = useCallback(
    async (interactionHandle: string) => {
      await dispatchAffordance(CatalogAffordanceId.SelectVariant, {
        variant_ref: interactionHandle,
      });
    },
    [dispatchAffordance],
  );
  const addItem = useCallback(
    async (variantHandle: string, quantity: number) => {
      await dispatchAffordance(CatalogAffordanceId.AddItem, {
        variant_ref: variantHandle,
        quantity,
      });
    },
    [dispatchAffordance],
  );
  const selectedVariant = product.variants.find(
    (variant) => variant.interaction_handle === product.selected_variant_handle,
  );

  return (
    <article data-catalog-product-detail={product.product_handle}>
      <header>
        <h1>{product.title}</h1>
        <p>
          {selectedVariant === undefined
            ? "Choose a variant to see its exact price."
            : formatCatalogPrice(selectedVariant.price)}
        </p>
      </header>
      {product.thumbnail_url === undefined ? null : (
        <img
          src={product.thumbnail_url}
          alt=""
          width="640"
          height="640"
        />
      )}
      {product.description === undefined ? null : <p>{product.description}</p>}
      <VariantSelector
        variants={product.variants}
        {...(product.selected_variant_handle === undefined
          ? {}
          : { selectedVariantHandle: product.selected_variant_handle })}
        onSelect={selectVariant}
      />
      <AddToCartAffordance
        key={selectedVariant?.interaction_handle ?? "no-selected-variant"}
        {...(selectedVariant === undefined ? {} : { selectedVariant })}
        onAdd={addItem}
      />
    </article>
  );
}

export function decodeProductDetail(
  props: RouteDeckSurfaceComponentProps["props"],
): CatalogProductDetailProjection {
  catalogExactKeys(props, "$.catalog.product_detail", ["product"]);
  const product = catalogRecord(props.product, "$.catalog.product_detail.product");
  catalogExactKeys(product, "$.catalog.product_detail.product", [
    "interaction_handle",
    "product_handle",
    "title",
    "description",
    "thumbnail_url",
    "image_urls",
    "options",
    "variants",
    "selected_variant_handle",
  ]);
  if (!Array.isArray(product.options)) {
    catalogInvalid("$.catalog.product_detail.product.options", "must be an array");
  }
  if (!Array.isArray(product.variants) || product.variants.length === 0) {
    catalogInvalid(
      "$.catalog.product_detail.product.variants",
      "must contain at least one variant",
    );
  }
  const variants = product.variants.map((variant, index) =>
    decodeCatalogVariant(
      variant,
      `$.catalog.product_detail.product.variants[${index}]`,
    ),
  );
  const selected =
    product.selected_variant_handle === undefined
      ? undefined
      : catalogString(
          product.selected_variant_handle,
          "$.catalog.product_detail.product.selected_variant_handle",
        );
  if (
    selected !== undefined &&
    !variants.some((variant) => variant.interaction_handle === selected)
  ) {
    catalogInvalid(
      "$.catalog.product_detail.product.selected_variant_handle",
      "does not identify a projected variant",
    );
  }
  return {
    interaction_handle: catalogString(
      product.interaction_handle,
      "$.catalog.product_detail.product.interaction_handle",
    ),
    product_handle: catalogString(
      product.product_handle,
      "$.catalog.product_detail.product.product_handle",
    ),
    title: catalogString(product.title, "$.catalog.product_detail.product.title"),
    ...(product.description === undefined
      ? {}
      : {
          description: catalogString(
            product.description,
            "$.catalog.product_detail.product.description",
          ),
        }),
    ...(product.thumbnail_url === undefined
      ? {}
      : {
          thumbnail_url: catalogString(
            product.thumbnail_url,
            "$.catalog.product_detail.product.thumbnail_url",
          ),
        }),
    image_urls: catalogStringArray(
      product.image_urls,
      "$.catalog.product_detail.product.image_urls",
    ),
    options: product.options.map((option, index) =>
      decodeCatalogOption(
        option,
        `$.catalog.product_detail.product.options[${index}]`,
      ),
    ),
    variants,
    ...(selected === undefined ? {} : { selected_variant_handle: selected }),
  };
}

function decodeCatalogOption(
  value: JsonValue | undefined,
  path: string,
): CatalogOptionProjection {
  const option = catalogRecord(value, path);
  catalogExactKeys(option, path, ["title", "values"]);
  return {
    title: catalogString(option.title, `${path}.title`),
    values: catalogStringArray(option.values, `${path}.values`),
  };
}
