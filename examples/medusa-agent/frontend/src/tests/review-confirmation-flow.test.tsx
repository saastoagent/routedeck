import "@testing-library/jest-dom/vitest";

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import {
  createPrivateFormState,
  createRouteDeckStore,
  type FrontendContract,
  type JsonObject,
  type RouteDeckProjection,
} from "@routedeck/core";
import {
  RouteDeckProvider,
  RouteDeckSurfaceHost,
} from "@routedeck/react";
import {
  routeDeckDispatchResultFixture,
  routeDeckProjectionFixture,
  ScriptedRouteDeckClient,
} from "@routedeck/testing";

import { CheckoutReviewAuthorityProvider } from "../features/checkout/CheckoutReviewAuthority";
import { medusaRouteDeckSurfaces } from "../routedeck/surfaces";

const PAYMENT_PROVIDER_REF = "pay_opaque_system_470a";
const CONTACT_FORM_HANDLE = "form_opaque_review_553f";
const REVIEW_ID = "review_opaque_42c1";
const ORDER_REF = "order_opaque_recovery_762b";
const CONFIRMATION_HANDLE = "confirmation_opaque_a190";
const PRIVATE_CART_ID = "cart_private_must_never_reach_browser";
const PRIVATE_ORDER_ID = "order_private_must_never_reach_browser";
const PRIVATE_ADDRESS = "18 Private Review Street";

it("moves from payment through reviewed recovery to verified confirmation", async () => {
  const fetchSpy = vi.spyOn(globalThis, "fetch");
  const storageSpy = vi.spyOn(Storage.prototype, "setItem");
  const client = new ScriptedRouteDeckClient();
  const dispatchSpy = vi.spyOn(client, "dispatch");
  const acceptSpy = vi.spyOn(client, "acceptReview");
  client.privateValues.set(CONTACT_FORM_HANDLE, {
    form_id: CONTACT_FORM_HANDLE,
    revision: 1,
    complete: true,
    session_version: 1,
    value: {
      email: "private-review@example.test",
      shipping_address: {
        first_name: "Review",
        last_name: "Buyer",
        address_1: PRIVATE_ADDRESS,
        postal_code: "10001",
        city: "Review City",
        country_code: "us",
      },
      billing_choice: "same_as_shipping",
    },
  });
  client.enqueueSession(paymentProjection());
  client.enqueueDispatch(operationResult("checkout.select_payment", 2, 2));
  client.enqueueDispatch({
    ...operationResult("checkout.place_order", 3, 3),
    disposition: "requires_review",
    outcome: "review_required",
    review: { id: REVIEW_ID, expires_at: "2030-01-01T00:00:00.000Z" },
  });
  client.enqueueDispatch({
    ...operationResult("checkout.place_order", 4, 4),
    disposition: "external_outcome_unknown",
    outcome: "external_outcome_unknown",
  });
  client.enqueueDispatch(operationResult("orders.reconcile", 5, 5));
  client.enqueueDispatch(operationResult("catalog.continue_shopping", 6, 5));

  const store = createRouteDeckStore({ client, bootstrapMode: "resume" });
  const privateForms = createPrivateFormState(client.privateForms);
  await store.bootstrap();
  client.enqueueSession(reviewProjection());
  client.enqueueSession(pendingReviewProjection());
  client.enqueueSession(unknownOutcomeProjection());
  client.enqueueSession(confirmationProjection());

  let requestSequence = 0;
  const rendered = render(
    <RouteDeckProvider
      store={store}
      contract={checkoutContract()}
      privateForms={privateForms}
      createRequestId={() => `review-request-${++requestSequence}`}
    >
      <CheckoutReviewAuthorityProvider>
        <RouteDeckSurfaceHost
          registry={medusaRouteDeckSurfaces}
          slots={["active", "review", "diagnostic"]}
        />
      </CheckoutReviewAuthorityProvider>
    </RouteDeckProvider>,
  );

  fireEvent.click(
    screen.getByRole("button", { name: "System / manual demo payment" }),
  );
  await screen.findByRole("heading", { name: "Review your order" });
  expect(
    screen.getByRole("button", { name: "Review and place order" }),
  ).toBeVisible();
  expect(
    screen.queryByRole("button", { name: "Place order" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Cancel order placement" }),
  ).not.toBeInTheDocument();
  await waitFor(() => expect(document.body.textContent).toContain(PRIVATE_ADDRESS));
  expect(dispatchSpy).toHaveBeenNthCalledWith(1, {
    operation_id: "checkout.select_payment",
    request_id: "review-request-1",
    expected_session_version: 1,
    arguments: { payment_provider_ref: PAYMENT_PROVIDER_REF },
  });
  expect(client.calls).toContain(`private.load:${CONTACT_FORM_HANDLE}`);

  fireEvent.click(
    screen.getByRole("button", { name: "Review and place order" }),
  );
  await screen.findByRole("button", { name: "Place order" });
  expect(
    screen.getByRole("button", { name: "Cancel order placement" }),
  ).toBeVisible();
  expect(dispatchSpy).toHaveBeenNthCalledWith(2, {
    operation_id: "checkout.place_order",
    request_id: "review-request-2",
    expected_session_version: 2,
    arguments: {},
  });

  fireEvent.click(screen.getByRole("button", { name: "Place order" }));
  await screen.findByText(
    "Order status could not be confirmed; do not submit again.",
  );
  expect(screen.queryByRole("heading", { name: "Order confirmed" })).not.toBeInTheDocument();
  expect(acceptSpy).toHaveBeenCalledWith(REVIEW_ID, {
    request_id: "review-request-3",
    expected_session_version: 3,
  });

  fireEvent.click(screen.getByRole("button", { name: "Check order status" }));
  await screen.findByRole("heading", { name: "Order confirmed" });
  expect(dispatchSpy).toHaveBeenNthCalledWith(3, {
    operation_id: "orders.reconcile",
    request_id: "review-request-4",
    expected_session_version: 4,
    arguments: { order_ref: ORDER_REF },
  });

  fireEvent.click(screen.getByRole("button", { name: "Continue shopping" }));
  await waitFor(() => expect(dispatchSpy).toHaveBeenCalledTimes(4));
  expect(dispatchSpy).toHaveBeenNthCalledWith(4, {
    operation_id: "catalog.continue_shopping",
    request_id: "review-request-5",
    expected_session_version: 5,
    arguments: {},
  });

  const publicEvidence = `${JSON.stringify(store.getState().projection)}\n${JSON.stringify(
    dispatchSpy.mock.calls,
  )}\n${document.body.textContent}`;
  for (const privateValue of [PRIVATE_CART_ID, PRIVATE_ORDER_ID, PRIVATE_ADDRESS]) {
    expect(publicEvidence).not.toContain(privateValue);
  }
  expect(storageSpy).not.toHaveBeenCalled();
  expect(
    fetchSpy.mock.calls.filter(([input]) => String(input).includes("/store/")),
  ).toHaveLength(0);

  rendered.unmount();
  privateForms.dispose();
  store.dispose();
  storageSpy.mockRestore();
  fetchSpy.mockRestore();
});

function paymentProjection(): RouteDeckProjection {
  return projectionAt(
    "checkout.payment",
    "/checkout/payment",
    1,
    1,
    projectedSurface("checkout.payment_method", "checkout.payment_method", {
      state: "ready",
      providers: [
        {
          payment_provider_ref: PAYMENT_PROVIDER_REF,
          label: "System / manual demo payment",
        },
      ],
    }),
    "checkout.select_payment",
  );
}

function reviewProjection(): RouteDeckProjection {
  const projection = projectionAt(
    "checkout.review",
    "/checkout/review",
    2,
    2,
    projectedSurface("checkout.order_review", "checkout.order_review", reviewProps()),
    "checkout.place_order",
  );
  projection.surfaces.review = [
    projectedSurface("checkout.review", "checkout.review", {}),
  ];
  return projection;
}

function pendingReviewProjection(): RouteDeckProjection {
  const projection = reviewProjection();
  projection.session_version = 3;
  projection.projection_version = 3;
  projection.surfaces.review = [
    projectedSurface("checkout.review", "checkout.review", {
      state: "pending",
      review_id: REVIEW_ID,
      expires_at: "2030-01-01T00:00:00.000Z",
    }),
  ];
  return projection;
}

function unknownOutcomeProjection(): RouteDeckProjection {
  const projection = reviewProjection();
  projection.session_version = 4;
  projection.projection_version = 4;
  projection.legal_operations = [
    {
      operation_id: "orders.reconcile",
      safety_class: "read_external",
      title: "Check order status",
      review_required: false,
    },
  ];
  projection.surfaces.diagnostic = [
    projectedSurface("checkout.recovery", "checkout.recovery", {
      state: "external_outcome_unknown",
      message: "Order status could not be confirmed; do not submit again.",
      correlation_id: "correlation-public-1",
      order_ref: ORDER_REF,
    }),
  ];
  return projection;
}

function confirmationProjection(): RouteDeckProjection {
  return projectionAt(
    "orders.confirmation",
    "/orders/{confirmation_handle}/confirmation",
    5,
    5,
    projectedSurface("orders.confirmation", "orders.confirmation", {
      confirmation_handle: CONFIRMATION_HANDLE,
      display_id: "1042",
      status: "pending",
      items: [
        {
          title: "Medusa T-Shirt",
          variant_title: "Black / Large",
          quantity: 1,
          unit_amount: 31,
          total: 31,
        },
      ],
      currency_code: "usd",
      subtotal: 31,
      shipping_total: 12,
      tax_total: 3,
      discount_total: 0,
      total: 46,
      shipping_label: "Standard delivery",
      payment_label: "System / manual demo payment",
    }),
    "catalog.continue_shopping",
  );
}

function reviewProps(): JsonObject {
  return {
    form_handle: CONTACT_FORM_HANDLE,
    items: [
      {
        title: "Medusa T-Shirt",
        variant_title: "Black / Large",
        quantity: 1,
        unit_amount: 31,
        total: 31,
      },
    ],
    currency_code: "usd",
    subtotal: 31,
    shipping_total: 12,
    tax_total: 3,
    discount_total: 0,
    total: 46,
    shipping_label: "Standard delivery",
    payment_label: "System / manual demo payment",
    contact_complete: true,
    billing_complete: true,
  };
}

function projectionAt(
  nodeId: string,
  routeTemplate: string,
  sessionVersion: number,
  projectionVersion: number,
  active: ReturnType<typeof projectedSurface>,
  operationId: string,
): RouteDeckProjection {
  const projection = routeDeckProjectionFixture({
    nodeId,
    routeTemplate,
    sessionVersion,
    projectionVersion,
  });
  projection.surfaces.active = active;
  projection.legal_operations = [
    {
      operation_id: operationId,
      safety_class: "write_external",
      title: operationId,
      review_required: operationId === "checkout.place_order",
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

function operationResult(
  operationId: string,
  sessionVersion: number,
  projectionVersion: number,
) {
  return {
    ...routeDeckDispatchResultFixture(),
    operation_id: operationId,
    request_id: `server-${sessionVersion}`,
    session_version: sessionVersion,
    projection_version: projectionVersion,
  };
}

function checkoutContract(): FrontendContract {
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
    name: "medusa-reviewed-confirmation-smoke",
    entry_node_id: "checkout.payment",
    nodes: {
      "checkout.payment": {
        id: "checkout.payment",
        title: "Payment",
        route_template: "/checkout/payment",
        deep_link_policy: "session_bound",
        operation_ids: ["checkout.select_payment"],
        surfaces: { active: "checkout.payment_method", ...emptySlots },
      },
      "checkout.review": {
        id: "checkout.review",
        title: "Review",
        route_template: "/checkout/review",
        deep_link_policy: "session_bound",
        operation_ids: ["checkout.place_order", "orders.reconcile"],
        surfaces: {
          active: "checkout.order_review",
          ...emptySlots,
          review: ["checkout.review"],
          diagnostic: ["checkout.recovery"],
        },
      },
      "orders.confirmation": {
        id: "orders.confirmation",
        title: "Order confirmed",
        route_template: "/orders/{confirmation_handle}/confirmation",
        deep_link_policy: "session_bound",
        operation_ids: ["catalog.continue_shopping"],
        surfaces: { active: "orders.confirmation", ...emptySlots },
      },
    },
    transitions: [],
    surfaces: {
      "checkout.payment_method": surfaceSpec(
        "checkout.payment_method",
        "select_payment",
        "select",
        "checkout.select_payment",
      ),
      "checkout.order_review": surfaceSpec(
        "checkout.order_review",
        "propose_order",
        "submit",
        "checkout.place_order",
      ),
      "checkout.review": surfaceSpec("checkout.review"),
      "checkout.recovery": surfaceSpec(
        "checkout.recovery",
        "reconcile_order",
        "retry",
        "orders.reconcile",
      ),
      "orders.confirmation": surfaceSpec(
        "orders.confirmation",
        "continue_shopping",
        "open",
        "catalog.continue_shopping",
      ),
    },
  };
}

function surfaceSpec(
  id: string,
  affordanceId?: string,
  event?: string,
  operationId?: string,
) {
  return {
    id,
    component: id,
    lifecycle: "stable" as const,
    public_props_schema: {},
    ...(affordanceId === undefined || event === undefined || operationId === undefined
      ? {}
      : {
          affordances: [
            { id: affordanceId, event, operation: { id: operationId } },
          ],
        }),
  };
}
