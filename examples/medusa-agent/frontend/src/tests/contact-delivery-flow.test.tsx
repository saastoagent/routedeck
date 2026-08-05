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

import { testSurfaceRegistryForContract } from "./surfaceRegistry";

const FORM_HANDLE = "form_opaque_checkout_81d3";
const SHIPPING_OPTION_HANDLE = "ship_opaque_checkout_f227";
const PRIVATE_CART_ID = "cart_private_must_never_reach_browser";
const PRIVATE_SHIPPING_ID = "so_private_must_never_reach_browser";
const EMAIL = "buyer@example.test";
const SHIPPING_ADDRESS = "1 Private Shipping Street";
const BILLING_ADDRESS = "9 Private Billing Avenue";
const PHONE = "+1 202 555 0147";

it("keeps contact private and selects projected delivery without Store API traffic", async () => {
  const fetchSpy = vi.spyOn(globalThis, "fetch");
  const storageSpy = vi.spyOn(Storage.prototype, "setItem");
  const client = new ScriptedRouteDeckClient();
  const dispatchSpy = vi.spyOn(client, "dispatch");
  const privateSaveSpy = vi.spyOn(client.privateForms, "save");
  client.privateValues.set(FORM_HANDLE, {
    form_id: FORM_HANDLE,
    revision: 0,
    complete: false,
    session_version: 1,
    value: {},
  });
  client.enqueueSession(contactProjection(1, 0));
  client.enqueueDispatch({
    ...routeDeckDispatchResultFixture(),
    operation_id: "checkout.save_contact",
    request_id: "checkout-request-2",
    session_version: 3,
    projection_version: 2,
  });
  client.enqueueDispatch({
    ...routeDeckDispatchResultFixture(),
    operation_id: "checkout.select_shipping",
    request_id: "checkout-request-3",
    session_version: 4,
    projection_version: 2,
  });

  const store = createRouteDeckStore({ client, bootstrapMode: "resume" });
  const privateForms = createPrivateFormState(client.privateForms);
  await store.bootstrap();
  let requestSequence = 0;
  const rendered = render(
    <RouteDeckProvider
      store={store}
      contract={checkoutContract()}
      privateForms={privateForms}
      createRequestId={() => `checkout-request-${++requestSequence}`}
    >
      <RouteDeckSurfaceHost
      registry={testSurfaceRegistryForContract(checkoutContract())}
        slots={["active"]}
      />
    </RouteDeckProvider>,
  );

  await screen.findByRole("heading", { name: "Contact and delivery address" });
  change("email", EMAIL);
  change("shipping_first_name", "Buyer");
  change("shipping_last_name", "Example");
  change("shipping_address_1", SHIPPING_ADDRESS);
  change("shipping_city", "Test City");
  change("shipping_postal_code", "10001");
  change("shipping_phone", PHONE);

  const shippingCountry = document.querySelector<HTMLSelectElement>(
    '[name="shipping_country_code"]',
  );
  expect(shippingCountry).toBeInstanceOf(HTMLSelectElement);
  expect(shippingCountry).toHaveValue("us");
  expect(shippingCountry).not.toHaveAttribute("pattern");

  fireEvent.click(
    screen.getByRole("radio", { name: "Use a separate billing address" }),
  );
  change("billing_first_name", "Buyer");
  change("billing_last_name", "Example");
  change("billing_address_1", BILLING_ADDRESS);
  change("billing_city", "Billing City");
  change("billing_postal_code", "20002");
  const billingCountry = document.querySelector<HTMLSelectElement>(
    '[name="billing_country_code"]',
  );
  expect(billingCountry).toBeInstanceOf(HTMLSelectElement);
  expect(billingCountry).toHaveValue("us");

  client.enqueueSession(contactProjection(2, 1));
  client.enqueueSession(deliveryProjection());
  fireEvent.click(
    screen.getByRole("button", { name: "Continue to delivery" }),
  );

  await screen.findByRole("heading", { name: "Delivery options" });
  expect(privateSaveSpy).toHaveBeenCalledOnce();
  expect(privateSaveSpy.mock.calls[0]?.[0]).toBe(FORM_HANDLE);
  expect(privateSaveSpy.mock.calls[0]?.[1]).toEqual({
    request_id: "checkout-request-1",
    expected_session_version: 1,
    complete: true,
    value: {
      email: EMAIL,
      shipping_address: {
        first_name: "Buyer",
        last_name: "Example",
        address_1: SHIPPING_ADDRESS,
        postal_code: "10001",
        city: "Test City",
        country_code: "us",
        phone: PHONE,
      },
      billing_choice: "separate",
      billing_address: {
        first_name: "Buyer",
        last_name: "Example",
        address_1: BILLING_ADDRESS,
        postal_code: "20002",
        city: "Billing City",
        country_code: "us",
      },
    },
  });
  expect(dispatchSpy).toHaveBeenNthCalledWith(1, {
    operation_id: "checkout.save_contact",
    request_id: "checkout-request-2",
    expected_session_version: 2,
    arguments: { form_handle: FORM_HANDLE },
  });
  expect(screen.queryByDisplayValue(EMAIL)).not.toBeInTheDocument();

  fireEvent.click(
    screen.getByRole("button", { name: /Standard delivery.*USD 12/ }),
  );
  await waitFor(() => expect(dispatchSpy).toHaveBeenCalledTimes(2));
  expect(dispatchSpy).toHaveBeenNthCalledWith(2, {
    operation_id: "checkout.select_shipping",
    request_id: "checkout-request-3",
    expected_session_version: 3,
    arguments: { shipping_option_ref: SHIPPING_OPTION_HANDLE },
  });

  const publicEvidence = `${JSON.stringify(store.getState().projection)}\n${JSON.stringify(
    dispatchSpy.mock.calls,
  )}\n${document.body.textContent}`;
  for (const privateValue of [
    EMAIL,
    SHIPPING_ADDRESS,
    BILLING_ADDRESS,
    PHONE,
    PRIVATE_CART_ID,
    PRIVATE_SHIPPING_ID,
  ]) {
    expect(publicEvidence).not.toContain(privateValue);
  }
  expect(client.calls).toContain(`private.save:${FORM_HANDLE}`);
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

it("reports synchronous contact extraction failures through RouteDeck", async () => {
  const client = new ScriptedRouteDeckClient();
  const privateSaveSpy = vi.spyOn(client.privateForms, "save");
  client.privateValues.set(FORM_HANDLE, {
    form_id: FORM_HANDLE,
    revision: 0,
    complete: false,
    session_version: 1,
    value: {},
  });
  client.enqueueSession(contactProjection(1, 0));
  const store = createRouteDeckStore({ client, bootstrapMode: "resume" });
  const privateForms = createPrivateFormState(client.privateForms);
  await store.bootstrap();
  const rendered = render(
    <RouteDeckProvider
      store={store}
      contract={checkoutContract()}
      privateForms={privateForms}
      createRequestId={() => "contact-error-request"}
    >
      <RouteDeckSurfaceHost
        registry={testSurfaceRegistryForContract(checkoutContract())}
        slots={["active"]}
      />
    </RouteDeckProvider>,
  );

  const heading = await screen.findByRole("heading", {
    name: "Contact and delivery address",
  });
  const form = heading.closest("form");
  if (form === null) throw new Error("Missing contact form");
  fireEvent.submit(form);

  expect(
    await screen.findByText("Private contact field email is required."),
  ).toBeInTheDocument();
  expect(privateSaveSpy).not.toHaveBeenCalled();

  rendered.unmount();
  privateForms.dispose();
  store.dispose();
});

function change(name: string, value: string): void {
  const input = document.querySelector<HTMLInputElement>(`[name="${name}"]`);
  if (!input) throw new Error(`Missing checkout input ${name}`);
  fireEvent.change(input, { target: { value } });
}

function contactProjection(
  sessionVersion: number,
  revision: number,
): RouteDeckProjection {
  const projection = routeDeckProjectionFixture({
    nodeId: "checkout.contact",
    routeTemplate: "/checkout/contact",
    sessionVersion,
    projectionVersion: 1,
  });
  projection.surfaces.active = projectedSurface(
    "checkout.contact_form",
    "checkout.contact_form",
    {
      form_handle: FORM_HANDLE,
      revision,
      complete: revision > 0,
      fields: [
        "email",
        "shipping_address",
        "billing_choice",
        "billing_address",
      ],
      billing_choices: ["same_as_shipping", "separate"],
      default_billing_choice: "same_as_shipping",
      country_choices: ["us"],
      default_country_code: "us",
    },
  );
  projection.legal_operations = [
    {
      operation_id: "checkout.save_contact",
      safety_class: "write_external",
      title: "Save guest contact",
      review_required: false,
      allowed_sources: ["surface"],
    },
  ];
  return projection;
}

function deliveryProjection(): RouteDeckProjection {
  const projection = routeDeckProjectionFixture({
    nodeId: "checkout.delivery",
    routeTemplate: "/checkout/delivery",
    sessionVersion: 3,
    projectionVersion: 2,
  });
  projection.surfaces.active = projectedSurface(
    "checkout.shipping_options",
    "checkout.shipping_options",
    {
      state: "ready",
      options: [
        {
          shipping_option_ref: SHIPPING_OPTION_HANDLE,
          label: "Standard delivery",
          amount: 12,
          currency_code: "usd",
        },
      ],
    },
  );
  projection.legal_operations = [
    {
      operation_id: "checkout.select_shipping",
      safety_class: "write_external",
      title: "Select delivery",
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
    name: "medusa-contact-delivery-smoke",
    entry_node_id: "checkout.contact",
    nodes: {
      "checkout.contact": {
        id: "checkout.contact",
        title: "Contact",
        route_template: "/checkout/contact",
        deep_link_policy: "session_bound",
        conversation_input: { enabled: true, disabled_message: null },
        operation_ids: ["checkout.save_contact"],
        surfaces: { active: "checkout.contact_form", ...emptySlots },
      },
      "checkout.delivery": {
        id: "checkout.delivery",
        title: "Delivery",
        route_template: "/checkout/delivery",
        deep_link_policy: "session_bound",
        conversation_input: { enabled: true, disabled_message: null },
        operation_ids: ["checkout.select_shipping"],
        surfaces: { active: "checkout.shipping_options", ...emptySlots },
      },
    },
    transitions: [],
    surfaces: {
      "checkout.contact_form": {
        id: "checkout.contact_form",
        component: "checkout.contact_form",
        lifecycle: "stable",
        public_props_schema: {},
        affordances: [
          {
            id: "save_contact",
            event: "submit",
            operation: { id: "checkout.save_contact" },
          },
        ],
      },
      "checkout.shipping_options": {
        id: "checkout.shipping_options",
        component: "checkout.shipping_options",
        lifecycle: "stable",
        public_props_schema: {},
        affordances: [
          {
            id: "select_shipping",
            event: "select",
            operation: { id: "checkout.select_shipping" },
          },
        ],
      },
    },
  };
}
