import "@testing-library/jest-dom/vitest";

import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import type {
  FrontendContract,
  JsonObject,
  RouteDeckProjection,
} from "@routedeck/core";
import { RouteDeckSurfaceHost } from "@routedeck/react";
import {
  renderRouteDeckComponent,
  routeDeckDispatchResultFixture,
  routeDeckProjectionFixture,
  ScriptedRouteDeckClient,
} from "@routedeck/testing";

import { testSurfaceRegistryForContract } from "./surfaceRegistry";

const PRODUCT_INTERACTION_HANDLE = "prd_opaque_buyer_7f3c";
const VARIANT_ONE_HANDLE = "var_opaque_buyer_31aa";
const VARIANT_TWO_HANDLE = "var_opaque_buyer_9bd2";
const PRIVATE_PRODUCT_ID = "prod_private_must_never_reach_browser";
const PRIVATE_VARIANT_ID = "variant_private_must_never_reach_browser";

it("keeps projected surfaces inert while RouteDeck reports an active chat turn", async () => {
  const client = new ScriptedRouteDeckClient();
  const dispatchSpy = vi.spyOn(client, "dispatch");
  const projection = catalogGridProjection() as RouteDeckProjection & {
    interaction: {
      phase: "active";
      owner: "chat";
    };
  };
  projection.interaction = { phase: "active", owner: "chat" };

  const harness = await renderRouteDeckComponent(
    <RouteDeckSurfaceHost
      registry={testSurfaceRegistryForContract(catalogContract())}
      slots={["active"]}
    />,
    {
      contract: catalogContract(),
      projection,
      client,
    },
  );

  const surface = screen
    .getByRole("link", { name: "Medusa T-Shirt" })
    .closest("[data-routedeck-surface]");
  expect(surface).not.toBeNull();
  expect(surface).toHaveAttribute("aria-busy", "true");
  expect(surface).toHaveAttribute("inert");
  fireEvent.click(screen.getByRole("link", { name: "Medusa T-Shirt" }));
  expect(dispatchSpy).not.toHaveBeenCalled();

  harness.dispose();
});

it("searches and clears the catalog through declared RouteDeck affordances", async () => {
  const client = new ScriptedRouteDeckClient();
  const dispatchSpy = vi.spyOn(client, "dispatch");
  client.enqueueDispatch({
    ...routeDeckDispatchResultFixture(),
    operation_id: "catalog.search",
    request_id: "component-request-1",
    session_version: 2,
    projection_version: 2,
  });

  const harness = await renderRouteDeckComponent(
    <RouteDeckSurfaceHost
      registry={testSurfaceRegistryForContract(catalogContract())}
      slots={["active"]}
    />,
    {
      contract: catalogContract(),
      projection: catalogGridProjection(),
      client,
    },
  );
  client.enqueueSession(catalogGridProjection("shirt", 2));

  fireEvent.change(screen.getByRole("searchbox", { name: "Search the catalog" }), {
    target: { value: "  shirt  " },
  });
  fireEvent.click(screen.getByRole("button", { name: "Search" }));

  await screen.findByRole("heading", { name: /Results for/ });
  expect(dispatchSpy).toHaveBeenNthCalledWith(1, {
    operation_id: "catalog.search",
    request_id: "component-request-1",
    expected_session_version: 1,
    arguments: { query: "shirt" },
  });

  client.enqueueDispatch({
    ...routeDeckDispatchResultFixture(),
    operation_id: "catalog.list",
    request_id: "component-request-2",
    session_version: 3,
    projection_version: 3,
  });
  client.enqueueSession(catalogGridProjection(undefined, 3));
  fireEvent.click(screen.getByRole("button", { name: "Clear search" }));

  await screen.findByRole("heading", { name: "Products" });
  expect(dispatchSpy).toHaveBeenNthCalledWith(2, {
    operation_id: "catalog.list",
    request_id: "component-request-2",
    expected_session_version: 2,
    arguments: {},
  });

  harness.dispose();
});

it("browses, opens, selects, and adds only through RouteDeck without Store API traffic", async () => {
  const fetchSpy = vi.spyOn(globalThis, "fetch");
  const client = new ScriptedRouteDeckClient();
  const dispatchSpy = vi.spyOn(client, "dispatch");
  client.enqueueDispatch({
    ...routeDeckDispatchResultFixture(),
    operation_id: "catalog.open_product",
    request_id: "component-request-1",
    session_version: 2,
    projection_version: 2,
  });

  const harness = await renderRouteDeckComponent(
    <RouteDeckSurfaceHost
      registry={testSurfaceRegistryForContract(catalogContract())}
      slots={["active"]}
    />,
    {
      contract: catalogContract(),
      projection: catalogGridProjection(),
      client,
    },
  );
  client.enqueueSession(catalogDetailProjection());

  const productLink = screen.getByRole("link", { name: "Medusa T-Shirt" });
  expect(productLink).toHaveAttribute("href", "/products/medusa-t-shirt");
  fireEvent.click(productLink);

  await screen.findByRole("group", { name: "Choose a variant" });
  const productHeader = screen
    .getByRole("heading", { name: "Medusa T-Shirt" })
    .closest("header");
  expect(productHeader).not.toBeNull();
  expect(
    within(productHeader!).getByText("Choose a variant to see its exact price."),
  ).toBeInTheDocument();
  expect(dispatchSpy).toHaveBeenNthCalledWith(1, {
    operation_id: "catalog.open_product",
    request_id: "component-request-1",
    expected_session_version: 1,
    arguments: { product_ref: PRODUCT_INTERACTION_HANDLE },
  });
  expect(harness.history.current()).toBe("/products/medusa-t-shirt");

  client.enqueueDispatch({
    ...routeDeckDispatchResultFixture(),
    operation_id: "catalog.select_variant",
    request_id: "component-request-2",
    session_version: 3,
    projection_version: 3,
  });
  client.enqueueSession(catalogDetailProjection(VARIANT_TWO_HANDLE, 3));
  fireEvent.click(
    screen.getByRole("radio", { name: /Black.*Large/ }),
  );

  await waitFor(() =>
    expect(
      screen.getByRole("radio", { name: /Black.*Large/ }),
    ).toBeChecked(),
  );
  expect(within(productHeader!).getByText("USD 31")).toBeInTheDocument();
  expect(
    within(productHeader!).queryByText(
      "Choose a variant to see its exact price.",
    ),
  ).not.toBeInTheDocument();
  expect(dispatchSpy).toHaveBeenNthCalledWith(2, {
    operation_id: "catalog.select_variant",
    request_id: "component-request-2",
    expected_session_version: 2,
    arguments: { variant_ref: VARIANT_TWO_HANDLE },
  });

  client.enqueueDispatch({
    ...routeDeckDispatchResultFixture(),
    operation_id: "cart.add_item",
    request_id: "component-request-3",
    session_version: 4,
    projection_version: 4,
  });
  client.enqueueSession(catalogDetailProjection(VARIANT_TWO_HANDLE, 4));

  const quantityInput = screen.getByRole("spinbutton", { name: "Quantity" });
  expect(quantityInput).toHaveValue(1);
  fireEvent.change(quantityInput, { target: { value: "2" } });
  fireEvent.click(screen.getByRole("button", { name: "Add to cart" }));

  await waitFor(() =>
    expect(dispatchSpy).toHaveBeenNthCalledWith(3, {
      operation_id: "cart.add_item",
      request_id: "component-request-3",
      expected_session_version: 3,
      arguments: { variant_ref: VARIANT_TWO_HANDLE, quantity: 2 },
    }),
  );

  const browserEvidence = `${document.body.textContent}\n${JSON.stringify(
    dispatchSpy.mock.calls,
  )}`;
  expect(browserEvidence).not.toContain(PRIVATE_PRODUCT_ID);
  expect(browserEvidence).not.toContain(PRIVATE_VARIANT_ID);
  expect(
    fetchSpy.mock.calls.filter(([input]) => String(input).includes("/store/")),
  ).toHaveLength(0);

  harness.dispose();
  fetchSpy.mockRestore();
});

function catalogGridProjection(
  query?: string,
  version = 1,
): RouteDeckProjection {
  const projection = routeDeckProjectionFixture({
    nodeId: "catalog.browse",
    routeTemplate: "/products",
    sessionVersion: version,
    projectionVersion: version,
    historyEntryId: 1,
  });
  projection.surfaces.active = projectedSurface(
    "catalog.product_grid",
    "catalog.product_grid",
    {
      products: [
        {
          interaction_handle: PRODUCT_INTERACTION_HANDLE,
          product_handle: "medusa-t-shirt",
          title: "Medusa T-Shirt",
          description: "A real projected catalog product.",
          price: { amount: 29, currency_code: "usd" },
          variant_count: 2,
        },
      ],
      count: 1,
      ...(query === undefined ? {} : { query }),
    },
  );
  projection.legal_operations = [
    {
      operation_id: "catalog.list",
      safety_class: "read_external",
      title: "Browse products",
      review_required: false,
      allowed_sources: ["surface"],
    },
    {
      operation_id: "catalog.search",
      safety_class: "read_external",
      title: "Search products",
      review_required: false,
      allowed_sources: ["surface"],
    },
    {
      operation_id: "catalog.open_product",
      safety_class: "navigation",
      title: "Open product",
      review_required: false,
      allowed_sources: ["surface"],
    },
    {
      operation_id: "cart.add_item",
      safety_class: "write_external",
      title: "Add selected item to cart",
      review_required: false,
      allowed_sources: ["surface"],
    },
  ];
  return projection;
}

function catalogDetailProjection(
  selectedVariantHandle?: string,
  version = 2,
): RouteDeckProjection {
  const projection = routeDeckProjectionFixture({
    nodeId: "catalog.product",
    routeTemplate: "/products/{product_handle}",
    routeParams: [{ name: "product_handle", value: "medusa-t-shirt" }],
    sessionVersion: version,
    projectionVersion: version,
    historyEntryId: 2,
  });
  projection.surfaces.active = projectedSurface(
    "catalog.product_detail",
    "catalog.product_detail",
    {
      product: {
        interaction_handle: PRODUCT_INTERACTION_HANDLE,
        product_handle: "medusa-t-shirt",
        title: "Medusa T-Shirt",
        description: "A real projected catalog product.",
        image_urls: [],
        options: [{ title: "Size", values: ["Small", "Large"] }],
        variants: [
          {
            interaction_handle: VARIANT_ONE_HANDLE,
            title: "Black / Small",
            price: { amount: 29, currency_code: "usd" },
            inventory_status: "in_stock",
            option_values: ["Black", "Small"],
          },
          {
            interaction_handle: VARIANT_TWO_HANDLE,
            title: "Black / Large",
            price: { amount: 31, currency_code: "usd" },
            inventory_status: "in_stock",
            option_values: ["Black", "Large"],
          },
        ],
        ...(selectedVariantHandle === undefined
          ? {}
          : { selected_variant_handle: selectedVariantHandle }),
      },
    },
  );
  projection.legal_operations = [
    {
      operation_id: "catalog.select_variant",
      safety_class: "state_selection",
      title: "Select variant",
      review_required: false,
      allowed_sources: ["surface"],
    },
  ];
  return projection;
}

function projectedSurface(
  surfaceId: string,
  component: string,
  props: JsonObject,
) {
  return {
    surface_id: surfaceId,
    component,
    props: Object.entries(props).map(([name, value]) => ({ name, value })),
  };
}

function catalogContract(): FrontendContract {
  const emptySlots = {
    frame: [],
    peer: [],
    detail: [],
    form: [],
    review: [],
    status: [],
    error: [],
    diagnostic: [],
  };
  return {
    name: "medusa-catalog-smoke",
    entry_node_id: "catalog.browse",
    nodes: {
      "catalog.browse": {
        id: "catalog.browse",
        title: "Products",
        route_template: "/products",
        deep_link_policy: "shareable",
        conversation_input: { enabled: true, disabled_message: null },
        operation_ids: [
          "catalog.list",
          "catalog.search",
          "catalog.open_product",
        ],
        surfaces: { active: "catalog.product_grid", ...emptySlots },
      },
      "catalog.product": {
        id: "catalog.product",
        title: "Product",
        route_template: "/products/{product_handle}",
        deep_link_policy: "shareable",
        conversation_input: { enabled: true, disabled_message: null },
        operation_ids: ["catalog.select_variant", "cart.add_item"],
        surfaces: { active: "catalog.product_detail", ...emptySlots },
      },
    },
    transitions: [],
    surfaces: {
      "catalog.product_grid": {
        id: "catalog.product_grid",
        component: "catalog.product_grid",
        lifecycle: "stable",
        public_props_schema: {},
        affordances: [
          {
            id: "search_products",
            event: "submit",
            operation: { id: "catalog.search" },
          },
          {
            id: "clear_search",
            event: "clear",
            operation: { id: "catalog.list" },
          },
          {
            id: "open_product",
            event: "open",
            operation: { id: "catalog.open_product" },
          },
        ],
      },
      "catalog.product_detail": {
        id: "catalog.product_detail",
        component: "catalog.product_detail",
        lifecycle: "stable",
        public_props_schema: {},
        affordances: [
          {
            id: "select_variant",
            event: "select",
            operation: { id: "catalog.select_variant" },
          },
          {
            id: "add_item",
            event: "submit",
            operation: { id: "cart.add_item" },
          },
        ],
      },
    },
  };
}
