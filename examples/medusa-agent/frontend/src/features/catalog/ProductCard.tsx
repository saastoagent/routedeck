import {
  useCallback,
  useMemo,
  useState,
  type MouseEvent,
} from "react";
import {
  RouteDeckLink,
  RouteDeckError,
} from "@routedeck/react";
import {
  RouteDeckStateError,
  type JsonValue,
} from "@routedeck/core";

export interface CatalogPriceProjection {
  amount: number;
  currency_code: string;
}

export interface CatalogProductCardProjection {
  interaction_handle: string;
  product_handle: string;
  title: string;
  description?: string;
  thumbnail_url?: string;
  price: CatalogPriceProjection;
  variant_count: number;
}

export interface ProductCardProps {
  product: CatalogProductCardProjection;
  onOpen(interactionHandle: string): Promise<void>;
}

export function ProductCard({ product, onOpen }: ProductCardProps) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const routeParams = useMemo(
    () => Object.freeze({ product_handle: product.product_handle }),
    [product.product_handle],
  );
  const openProduct = useCallback(
    (event: MouseEvent<HTMLAnchorElement>) => {
      if (
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey
      ) {
        return;
      }
      event.preventDefault();
      if (pending) return;
      setPending(true);
      setError(null);
      void onOpen(product.interaction_handle)
        .catch((caught: unknown) => {
          setError(
            caught instanceof Error
              ? caught
              : new Error("RouteDeck could not open this product."),
          );
        })
        .finally(() => setPending(false));
    },
    [onOpen, pending, product.interaction_handle],
  );

  return (
    <article data-catalog-product={product.product_handle}>
      {product.thumbnail_url === undefined ? null : (
        <img
          src={product.thumbnail_url}
          alt=""
          loading="lazy"
          width="320"
          height="320"
        />
      )}
      <h2>
        <RouteDeckLink
          nodeId="catalog.product"
          params={routeParams}
          onClick={openProduct}
          aria-busy={pending}
        >
          {product.title}
        </RouteDeckLink>
      </h2>
      {product.description === undefined ? null : <p>{product.description}</p>}
      <p>{formatCatalogPrice(product.price)}</p>
      <small>
        {product.variant_count} {product.variant_count === 1 ? "variant" : "variants"}
      </small>
      {error === null ? null : (
        <RouteDeckError code="catalog_open_failed" message={error.message} />
      )}
    </article>
  );
}

export function decodeCatalogProductCard(
  value: JsonValue | undefined,
  path: string,
): CatalogProductCardProjection {
  const record = catalogRecord(value, path);
  catalogExactKeys(record, path, [
    "interaction_handle",
    "product_handle",
    "title",
    "description",
    "thumbnail_url",
    "price",
    "variant_count",
  ]);
  return {
    interaction_handle: catalogString(
      record.interaction_handle,
      `${path}.interaction_handle`,
    ),
    product_handle: catalogString(
      record.product_handle,
      `${path}.product_handle`,
    ),
    title: catalogString(record.title, `${path}.title`),
    ...catalogOptionalString(record.description, `${path}.description`, "description"),
    ...catalogOptionalString(
      record.thumbnail_url,
      `${path}.thumbnail_url`,
      "thumbnail_url",
    ),
    price: decodeCatalogPrice(record.price, `${path}.price`),
    variant_count: catalogInteger(
      record.variant_count,
      `${path}.variant_count`,
      1,
    ),
  };
}

export function decodeCatalogPrice(
  value: JsonValue | undefined,
  path: string,
): CatalogPriceProjection {
  const record = catalogRecord(value, path);
  catalogExactKeys(record, path, ["amount", "currency_code"]);
  const currency = catalogString(record.currency_code, `${path}.currency_code`);
  if (currency.length !== 3) catalogInvalid(path, "currency_code must have length 3");
  return {
    amount: catalogInteger(record.amount, `${path}.amount`, 0),
    currency_code: currency,
  };
}

export function formatCatalogPrice(price: CatalogPriceProjection): string {
  return `${price.currency_code.toUpperCase()} ${new Intl.NumberFormat().format(price.amount)}`;
}

export function catalogRecord(
  value: JsonValue | undefined,
  path: string,
): Record<string, JsonValue> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    catalogInvalid(path, "must be an object");
  }
  return value as Record<string, JsonValue>;
}

export function catalogString(
  value: JsonValue | undefined,
  path: string,
): string {
  if (typeof value !== "string" || value.length === 0) {
    catalogInvalid(path, "must be a non-empty string");
  }
  return value;
}

export function catalogInteger(
  value: JsonValue | undefined,
  path: string,
  minimum?: number,
): number {
  if (
    typeof value !== "number" ||
    !Number.isInteger(value) ||
    (minimum !== undefined && value < minimum)
  ) {
    catalogInvalid(path, "must be a valid integer");
  }
  return value;
}

export function catalogStringArray(
  value: JsonValue | undefined,
  path: string,
): string[] {
  if (!Array.isArray(value)) catalogInvalid(path, "must be an array");
  return value.map((item, index) => catalogString(item, `${path}[${index}]`));
}

export function catalogExactKeys(
  record: Record<string, JsonValue>,
  path: string,
  allowedKeys: readonly string[],
): void {
  const allowed = new Set(allowedKeys);
  const extra = Object.keys(record).find((key) => !allowed.has(key));
  if (extra !== undefined) catalogInvalid(path, `contains undeclared field ${extra}`);
}

function catalogOptionalString<K extends string>(
  value: JsonValue | undefined,
  path: string,
  key: K,
): { [P in K]?: string } {
  return value === undefined ? {} : { [key]: catalogString(value, path) } as {
    [P in K]?: string;
  };
}

export function catalogInvalid(path: string, message: string): never {
  throw new RouteDeckStateError(
    "catalog_projection_invalid",
    `Catalog projection ${path} ${message}.`,
  );
}
