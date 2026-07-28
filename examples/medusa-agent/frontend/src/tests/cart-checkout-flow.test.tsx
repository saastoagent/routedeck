import "@testing-library/jest-dom/vitest";

import { fireEvent, screen, waitFor } from "@testing-library/react";
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

it("starts checkout exactly once from a non-empty cart", async () => {
  const client = new ScriptedRouteDeckClient();
  const dispatchSpy = vi.spyOn(client, "dispatch");
  const projection = cartProjection(1, true);
  const harness = await renderRouteDeckComponent(
    <RouteDeckSurfaceHost
      registry={testSurfaceRegistryForContract(cartContract())}
      slots={["active"]}
    />,
    { contract: cartContract(), projection, client },
  );
  client.enqueueDispatch({
    ...routeDeckDispatchResultFixture(),
    operation_id: "checkout.start",
    request_id: "component-request-1",
    session_version: 2,
    projection_version: 2,
  });
  client.enqueueSession(cartProjection(2, true));

  const checkout = screen.getByRole("button", { name: "Checkout" });
  fireEvent.click(checkout);
  fireEvent.click(checkout);

  await waitFor(() => expect(dispatchSpy).toHaveBeenCalledOnce());
  expect(dispatchSpy).toHaveBeenCalledWith({
    operation_id: "checkout.start",
    request_id: "component-request-1",
    expected_session_version: 1,
    arguments: {},
  });

  harness.unmount();
});

it("does not render checkout for an empty cart", async () => {
  const harness = await renderRouteDeckComponent(
    <RouteDeckSurfaceHost
      registry={testSurfaceRegistryForContract(cartContract())}
      slots={["active"]}
    />,
    {
      contract: cartContract(),
      projection: cartProjection(1, false),
      client: new ScriptedRouteDeckClient(),
    },
  );

  expect(
    screen.queryByRole("button", { name: "Checkout" }),
  ).not.toBeInTheDocument();

  harness.unmount();
});

function cartProjection(
  sessionVersion: number,
  hasItem: boolean,
): RouteDeckProjection {
  const projection = routeDeckProjectionFixture({
    nodeId: "cart.summary",
    routeTemplate: "/cart",
    sessionVersion,
    projectionVersion: sessionVersion,
  });
  projection.surfaces.active = projectedSurface("cart.summary", {
    cart_ref: "cart-public-1",
    currency_code: "gbp",
    items: hasItem
      ? [
          {
            line_item_ref: "line-public-1",
            title: "Linen shirt",
            selected_options: ["Large"],
            quantity: 1,
            unit_price: 4900,
            line_total: 4900,
          },
        ]
      : [],
    subtotal: hasItem ? 4900 : 0,
    shipping_total: 0,
    tax_total: 0,
    discount_total: 0,
    total: hasItem ? 4900 : 0,
  });
  projection.navigation.resume_handle = "resume-cart-checkout";
  projection.legal_operations = hasItem
    ? [
        {
          operation_id: "checkout.start",
          safety_class: "navigation",
          title: "Start checkout",
          review_required: false,
        },
      ]
    : [];
  return projection;
}

function projectedSurface(surfaceId: string, props: JsonObject) {
  return {
    surface_id: surfaceId,
    component: surfaceId,
    props: Object.entries(props).map(([name, value]) => ({ name, value })),
  };
}

function cartContract(): FrontendContract {
  return {
    name: "medusa-cart-checkout-smoke",
    entry_node_id: "cart.summary",
    nodes: {
      "cart.summary": {
        id: "cart.summary",
        title: "Cart",
        route_template: "/cart",
        deep_link_policy: "session_bound",
        conversation_input: { enabled: true, disabled_message: null },
        operation_ids: ["checkout.start"],
        surfaces: {
          active: "cart.summary",
          frame: [],
          peer: [],
          detail: [],
          form: [],
          review: [],
          status: [],
          error: [],
          diagnostic: [],
        },
      },
    },
    transitions: [],
    surfaces: {
      "cart.summary": {
        id: "cart.summary",
        component: "cart.summary",
        lifecycle: "stable",
        public_props_schema: {},
        affordances: [
          {
            id: "start_checkout",
            event: "submit",
            operation: { id: "checkout.start" },
          },
        ],
      },
    },
  };
}
