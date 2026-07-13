import {
  useCallback,
  useEffect,
  useId,
  useState,
  type FormEvent,
} from "react";
import type { RouteDeckSurfaceComponentProps } from "@routedeck/react";

import {
  ProductCard,
  catalogExactKeys,
  catalogInvalid,
  catalogInteger,
  catalogString,
  decodeCatalogProductCard,
  type CatalogProductCardProjection,
} from "./ProductCard";
import { CatalogAffordanceId } from "./affordances";

interface CatalogGridProjection {
  products: CatalogProductCardProjection[];
  count: number;
  query?: string;
}

export function ProductGridSurface({
  props,
  dispatchAffordance,
}: RouteDeckSurfaceComponentProps) {
  const collection = decodeCatalogGrid(props);
  const searchInputId = useId();
  const [query, setQuery] = useState(collection.query ?? "");
  useEffect(() => {
    setQuery(collection.query ?? "");
  }, [collection.query]);
  const searchProducts = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      const submittedQuery = query.trim();
      if (!submittedQuery) return;
      await dispatchAffordance(CatalogAffordanceId.SearchProducts, {
        query: submittedQuery,
      });
    },
    [dispatchAffordance, query],
  );
  const clearSearch = useCallback(async () => {
    await dispatchAffordance(CatalogAffordanceId.ClearSearch, {});
  }, [dispatchAffordance]);
  const openProduct = useCallback(
    async (interactionHandle: string) => {
      await dispatchAffordance(CatalogAffordanceId.OpenProduct, {
        product_ref: interactionHandle,
      });
    },
    [dispatchAffordance],
  );

  return (
    <section aria-labelledby="catalog-products-title">
      <header>
        <h1 id="catalog-products-title">
          {collection.query === undefined
            ? "Products"
            : `Results for “${collection.query}”`}
        </h1>
        <p>{collection.count} products</p>
      </header>
      <form aria-label="Search products" onSubmit={searchProducts}>
        <label htmlFor={searchInputId}>Search the catalog</label>
        <div data-catalog-search-controls="">
          <input
            id={searchInputId}
            type="search"
            value={query}
            onChange={(event) => setQuery(event.currentTarget.value)}
            autoComplete="off"
          />
          <button type="submit" disabled={!query.trim()}>
            Search
          </button>
          {collection.query === undefined ? null : (
            <button type="button" onClick={() => void clearSearch()}>
              Clear search
            </button>
          )}
        </div>
      </form>
      {collection.products.length === 0 ? (
        <p>No products are currently available.</p>
      ) : (
        <div data-catalog-product-grid="">
          {collection.products.map((product) => (
            <ProductCard
              key={product.interaction_handle}
              product={product}
              onOpen={openProduct}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function decodeCatalogGrid(
  props: RouteDeckSurfaceComponentProps["props"],
): CatalogGridProjection {
  catalogExactKeys(props, "$.catalog.product_grid", [
    "products",
    "count",
    "query",
  ]);
  const productsValue = props.products;
  if (!Array.isArray(productsValue)) {
    catalogInvalid("$.catalog.product_grid.products", "must be an array");
  }
  const products = productsValue.map((product, index) =>
    decodeCatalogProductCard(product, `$.catalog.product_grid.products[${index}]`),
  );
  const count = catalogInteger(props.count, "$.catalog.product_grid.count", 0);
  if (count < products.length) {
    catalogInvalid(
      "$.catalog.product_grid.count",
      "cannot be smaller than the projected product page",
    );
  }
  return {
    products,
    count,
    ...(props.query === undefined
      ? {}
      : { query: catalogString(props.query, "$.catalog.product_grid.query") }),
  };
}
