import "@testing-library/jest-dom/vitest";

import { fireEvent, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import type {
  FrontendContract,
  JsonObject,
  RouteDeckPrivateFormSnapshot,
  RouteDeckProjection,
} from "@routedeck/core";
import {
  NavGraphInspector,
  RouteDeckLink,
  RouteDeckNavigationControls,
  RouteDeckReview,
  RouteDeckStatus,
  RouteDeckSurfaceHost,
} from "@routedeck/react";
import {
  renderRouteDeckComponent,
  routeDeckDispatchResultFixture,
  routeDeckProjectionFixture,
  ScriptedRouteDeckClient,
} from "@routedeck/testing";

import type { AgentChatClient } from "../app/chatClient";
import { medusaRouteDeckSurfaces } from "../routedeck/surfaces";
import { AgentShell } from "../ui/AgentShell";

const REVIEW_ID = "review_opaque_shell_82c4";
const CONTACT_FORM_HANDLE = "form_opaque_shell_30f1";
const idleChatClient: AgentChatClient = Object.freeze({
  async *stream() {},
});

it("runs the provider, surface, dispatch, review, navigation, and read-only inspector flow", async () => {
  const contract = frontendContract();
  const projection = routeDeckProjectionFixture({
    nodeId: "buyer.home",
    routeTemplate: "/",
    sessionVersion: 1,
  });
  projection.surfaces.active = {
    surface_id: "buyer.welcome",
    component: "buyer.welcome",
    props: [],
  };
  projection.legal_operations = [
    {
      operation_id: "catalog.list",
      safety_class: "read_external",
      title: "Browse products",
      review_required: false,
    },
  ];
  projection.navigation.can_back = true;
  projection.navigation.back_node_id = "buyer.home";

  const client = new ScriptedRouteDeckClient();
  client.enqueueDispatch({
    ...routeDeckDispatchResultFixture(),
    operation_id: "catalog.list",
    request_id: "component-request-1",
    session_version: 2,
  });
  client.enqueueDispatch({
    ...routeDeckDispatchResultFixture(),
    operation_id: "checkout.place_order",
    request_id: "component-request-2",
    session_version: 3,
  });
  const back = vi.fn();
  const harness = await renderRouteDeckComponent(
    <>
      <RouteDeckSurfaceHost
        registry={medusaRouteDeckSurfaces}
        slots={["active"]}
      />
      <RouteDeckLink nodeId="catalog.browse">Open catalog route</RouteDeckLink>
      <RouteDeckNavigationControls />
      <RouteDeckReview reviewId="review-1" />
      <RouteDeckStatus />
      <NavGraphInspector
        contract={contract}
        edges={[
          {
            id: "buyer-to-catalog",
            from: "buyer.home",
            to: "catalog.browse",
          },
        ]}
        currentNodeId="buyer.home"
        reachableNodeIds={["catalog.browse"]}
      />
    </>,
    {
      contract,
      projection,
      client,
      navigationActions: { back },
    },
  );

  expect(
    screen.getByRole("heading", { name: "Shop with Medusa" }),
  ).toBeVisible();

  fireEvent.click(screen.getByRole("button", { name: "Browse products" }));
  await waitFor(() => expect(client.calls).toContain("dispatch"));
  await waitFor(() =>
    expect(harness.store.getState().sessionVersion).toBe(2),
  );

  client.enqueueSession({ ...projection, session_version: 3 });
  fireEvent.click(screen.getByRole("button", { name: "Accept" }));
  await waitFor(() =>
    expect(client.calls).toContain("review.accept:review-1"),
  );

  fireEvent.click(screen.getByRole("button", { name: "Back" }));
  expect(back).toHaveBeenCalledOnce();

  client.enqueueNavigation({
    ...projection,
    current: { node_id: "catalog.browse", route_params: [] },
    navigation: {
      ...projection.navigation,
      current: { node_id: "catalog.browse", route_params: [] },
      current_entry_id: 2,
      route_template: "/products",
      can_back: true,
      back_node_id: "buyer.home",
    },
    session_version: 4,
    projection_version: 2,
  });
  fireEvent.click(screen.getByRole("link", { name: "Open catalog route" }));
  await waitFor(() => expect(harness.history.current()).toBe("/products"));

  const dispatchCallsBeforeInspector = client.calls.filter(
    (call) => call === "dispatch",
  ).length;
  const historyBeforeInspector = harness.history.current();
  fireEvent.click(await screen.findByRole("button", { name: "Catalog" }));
  expect(screen.getByText("catalog.browse")).toBeVisible();
  expect(
    client.calls.filter((call) => call === "dispatch").length,
  ).toBe(dispatchCallsBeforeInspector);
  expect(harness.history.current()).toBe(historyBeforeInspector);

  harness.dispose();
});

it("keeps proposal and acceptance disabled while private delivery hydrates", async () => {
  let resolveLoad!: (snapshot: RouteDeckPrivateFormSnapshot) => void;
  const client = new ScriptedRouteDeckClient();
  client.privateForms.load = vi.fn(
    (_formId: string) =>
      new Promise<RouteDeckPrivateFormSnapshot>((resolve) => {
        resolveLoad = resolve;
      }),
  );

  const harness = await renderRouteDeckComponent(
    <AgentShell registry={medusaRouteDeckSurfaces} client={idleChatClient} />,
    {
      contract: reviewShellContract(),
      projection: pendingReviewProjection(),
      client,
    },
  );

  await waitFor(() => expect(client.privateForms.load).toHaveBeenCalledOnce());
  expect(
    screen.getByRole("button", { name: "Review and place order" }),
  ).toBeDisabled();
  expect(screen.getByRole("button", { name: "Place order" })).toBeDisabled();

  resolveLoad(privateReviewSnapshot());
  await screen.findByRole("heading", { name: "Delivery address" });
  harness.dispose();
});

it("keeps proposal and acceptance disabled when the hydrated address is invalid", async () => {
  const client = new ScriptedRouteDeckClient();
  client.privateValues.set(CONTACT_FORM_HANDLE, {
    ...privateReviewSnapshot(),
    value: {
      shipping_address: {
        first_name: "Review",
        last_name: "Buyer",
      },
    },
  });

  const harness = await renderRouteDeckComponent(
    <AgentShell registry={medusaRouteDeckSurfaces} client={idleChatClient} />,
    {
      contract: reviewShellContract(),
      projection: pendingReviewProjection(),
      client,
    },
  );

  await screen.findByRole("alert");
  expect(
    screen.getByRole("button", { name: "Review and place order" }),
  ).toBeDisabled();
  expect(screen.getByRole("button", { name: "Place order" })).toBeDisabled();
  harness.dispose();
});

it("enables proposal and acceptance after private delivery hydration succeeds", async () => {
  const client = new ScriptedRouteDeckClient();
  client.privateValues.set(CONTACT_FORM_HANDLE, privateReviewSnapshot());

  const harness = await renderRouteDeckComponent(
    <AgentShell registry={medusaRouteDeckSurfaces} client={idleChatClient} />,
    {
      contract: reviewShellContract(),
      projection: pendingReviewProjection(),
      client,
    },
  );

  const orderReviewHeading = screen.getByRole("heading", {
    name: "Review your order",
  });
  const routeDeckReviewHeading = screen.getByRole("heading", {
    name: "Confirm order placement",
  });
  expect(orderReviewHeading).toBeVisible();
  expect(routeDeckReviewHeading).toBeVisible();
  await screen.findByRole("heading", { name: "Delivery address" });
  expect(
    screen.getByRole("button", { name: "Review and place order" }),
  ).toBeEnabled();
  expect(screen.getByRole("button", { name: "Place order" })).toBeEnabled();
  expect(
    screen.getByRole("button", { name: "Cancel order placement" }),
  ).toBeEnabled();
  expect(
    orderReviewHeading.compareDocumentPosition(routeDeckReviewHeading) &
      Node.DOCUMENT_POSITION_FOLLOWING,
  ).toBeTruthy();

  harness.dispose();
});

it("keeps rejection available when private delivery hydration fails", async () => {
  const client = new ScriptedRouteDeckClient();
  client.privateForms.load = vi.fn(async (_formId: string) => {
    throw new Error("Private delivery address could not be loaded.");
  });
  client.enqueueDispatch({
    ...routeDeckDispatchResultFixture(),
    operation_id: "checkout.place_order",
    request_id: "review-rejected-server",
    session_version: 8,
    projection_version: 8,
  });

  const harness = await renderRouteDeckComponent(
    <AgentShell registry={medusaRouteDeckSurfaces} client={idleChatClient} />,
    {
      contract: reviewShellContract(),
      projection: pendingReviewProjection(),
      client,
    },
  );

  await screen.findByText("Private delivery address could not be loaded.");
  expect(screen.getByRole("button", { name: "Place order" })).toBeDisabled();
  const reject = screen.getByRole("button", {
    name: "Cancel order placement",
  });
  expect(reject).toBeEnabled();
  fireEvent.click(reject);
  await waitFor(() =>
    expect(client.calls).toContain(`review.reject:${REVIEW_ID}`),
  );
  harness.dispose();
});

function pendingReviewProjection(): RouteDeckProjection {
  const projection = routeDeckProjectionFixture({
    nodeId: "checkout.review",
    routeTemplate: "/checkout/review",
    sessionVersion: 7,
    projectionVersion: 7,
  });
  projection.surfaces.active = projectedSurface(
    "checkout.order_review",
    "checkout.order_review",
    {
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
    },
  );
  projection.surfaces.review = [
    projectedSurface("checkout.review", "checkout.review", {
      state: "pending",
      review_id: REVIEW_ID,
      expires_at: "2030-01-01T00:00:00.000Z",
    }),
  ];
  projection.navigation.resume_handle = "resume-review-shell";
  projection.legal_operations = [
    {
      operation_id: "checkout.place_order",
      safety_class: "write_external",
      title: "Place order",
      review_required: true,
    },
  ];
  return projection;
}

function privateReviewSnapshot(): RouteDeckPrivateFormSnapshot {
  return {
    form_id: CONTACT_FORM_HANDLE,
    revision: 1,
    complete: true,
    session_version: 7,
    value: {
      shipping_address: {
        first_name: "Review",
        last_name: "Buyer",
        address_1: "42 Test Street",
        city: "Test City",
        postal_code: "10001",
        country_code: "us",
      },
    },
  };
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

function reviewShellContract(): FrontendContract {
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
    name: "medusa-agent-shell-review",
    entry_node_id: "checkout.review",
    nodes: {
      "checkout.review": {
        id: "checkout.review",
        title: "Review",
        route_template: "/checkout/review",
        deep_link_policy: "session_bound",
        operation_ids: ["checkout.place_order"],
        surfaces: {
          active: "checkout.order_review",
          ...emptySlots,
          review: ["checkout.review"],
        },
      },
    },
    transitions: [],
    surfaces: {
      "checkout.order_review": {
        id: "checkout.order_review",
        component: "checkout.order_review",
        lifecycle: "stable",
        public_props_schema: {},
        affordances: [
          {
            id: "propose_order",
            event: "submit",
            operation: { id: "checkout.place_order" },
          },
        ],
      },
      "checkout.review": {
        id: "checkout.review",
        component: "checkout.review",
        lifecycle: "stable",
        public_props_schema: {},
      },
    },
  };
}

function frontendContract(): FrontendContract {
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
    name: "medusa-component-smoke",
    entry_node_id: "buyer.home",
    nodes: {
      "buyer.home": {
        id: "buyer.home",
        title: "Welcome",
        route_template: "/",
        deep_link_policy: "shareable",
        operation_ids: ["catalog.list"],
        surfaces: { active: "buyer.welcome", ...emptySlots },
      },
      "catalog.browse": {
        id: "catalog.browse",
        title: "Catalog",
        route_template: "/products",
        deep_link_policy: "shareable",
        operation_ids: [],
        surfaces: { active: "buyer.welcome", ...emptySlots },
      },
    },
    transitions: [
      {
        source: "buyer.home",
        operation_id: "catalog.list",
        outcome: "listed",
        target: "catalog.browse",
      },
    ],
    surfaces: {
      "buyer.welcome": {
        id: "buyer.welcome",
        component: "buyer.welcome",
        lifecycle: "stable",
        public_props_schema: {},
        affordances: [
          {
            id: "browse_products",
            event: "open",
            operation: { id: "catalog.list" },
          },
        ],
      },
    },
  };
}
