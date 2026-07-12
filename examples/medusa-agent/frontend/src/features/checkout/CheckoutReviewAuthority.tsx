import { createContext, useContext, type ReactNode } from "react";
import { RouteDeckStateError, type JsonObject } from "@routedeck/core";
import {
  RouteDeckError,
  RouteDeckPrivateForm,
  projectedSurfaceProps,
  useRouteDeckSurface,
  type RouteDeckPrivateFormBinding,
} from "@routedeck/react";

import { checkoutRecord, checkoutString } from "./PaymentMethodSurface";

export interface CheckoutDeliveryAddress {
  firstName: string;
  lastName: string;
  address1: string;
  city: string;
  postalCode: string;
  countryCode: string;
}

export type CheckoutReviewAuthority =
  | { state: "inactive" }
  | { state: "loading" }
  | { state: "failed"; error: Error }
  | { state: "ready"; address: CheckoutDeliveryAddress };

const CheckoutReviewAuthorityContext =
  createContext<CheckoutReviewAuthority | null>(null);
const INACTIVE_AUTHORITY: CheckoutReviewAuthority = Object.freeze({
  state: "inactive",
});

export function CheckoutReviewAuthorityProvider({
  children,
}: {
  children: ReactNode;
}) {
  const activeSurface = useRouteDeckSurface("active");
  if (activeSurface?.surface_id !== "checkout.order_review") {
    return (
      <CheckoutReviewAuthorityContext.Provider value={INACTIVE_AUTHORITY}>
        {children}
      </CheckoutReviewAuthorityContext.Provider>
    );
  }
  if (activeSurface.component !== "checkout.order_review") {
    throw new RouteDeckStateError(
      "checkout_review_surface_mismatch",
      "The checkout review authority requires the canonical order-review surface.",
    );
  }
  const formHandle = checkoutString(
    projectedSurfaceProps(activeSurface).form_handle,
    "$.checkout.order_review.form_handle",
  );
  return (
    <RouteDeckPrivateForm formId={formHandle} loadOnMount>
      {(binding) => (
        <CheckoutReviewAuthorityContext.Provider
          value={resolveCheckoutReviewAuthority(binding)}
        >
          {children}
        </CheckoutReviewAuthorityContext.Provider>
      )}
    </RouteDeckPrivateForm>
  );
}

export function useCheckoutReviewAuthority(): CheckoutReviewAuthority {
  const authority = useContext(CheckoutReviewAuthorityContext);
  if (authority === null) {
    throw new RouteDeckStateError(
      "checkout_review_authority_required",
      "Checkout review surfaces require CheckoutReviewAuthorityProvider.",
    );
  }
  return authority;
}

export function CheckoutReviewAuthorityStatus({
  authority,
}: {
  authority: CheckoutReviewAuthority;
}) {
  if (authority.state === "loading") {
    return <p role="status">Loading private address summary…</p>;
  }
  if (authority.state === "failed") {
    return (
      <RouteDeckError
        code="review_address_unavailable"
        message={authority.error.message}
      />
    );
  }
  if (authority.state === "inactive") {
    return (
      <RouteDeckError
        code="review_address_unavailable"
        message="The private delivery address is unavailable for this review."
      />
    );
  }
  return (
    <section aria-labelledby="private-address-summary-title">
      <h2 id="private-address-summary-title">Delivery address</h2>
      <address>
        {authority.address.firstName} {authority.address.lastName}
        <br />
        {authority.address.address1}
        <br />
        {authority.address.city}, {authority.address.postalCode}
        <br />
        {authority.address.countryCode.toUpperCase()}
      </address>
    </section>
  );
}

function resolveCheckoutReviewAuthority(
  binding: RouteDeckPrivateFormBinding,
): CheckoutReviewAuthority {
  if (binding.error !== null) {
    return { state: "failed", error: binding.error };
  }
  if (binding.pending || binding.snapshot === null) {
    return { state: "loading" };
  }
  if (!binding.snapshot.complete) {
    return {
      state: "failed",
      error: new RouteDeckStateError(
        "checkout_review_private_form_incomplete",
        "The private delivery address is incomplete.",
      ),
    };
  }
  try {
    return {
      state: "ready",
      address: decodePrivateAddress(binding.snapshot.value),
    };
  } catch (caught) {
    return {
      state: "failed",
      error:
        caught instanceof Error
          ? caught
          : new Error("The private delivery address could not be decoded."),
    };
  }
}

function decodePrivateAddress(value: JsonObject): CheckoutDeliveryAddress {
  const shipping = checkoutRecord(
    value.shipping_address,
    "$.private.shipping_address",
  );
  return {
    firstName: checkoutString(
      shipping.first_name,
      "$.private.shipping_address.first_name",
    ),
    lastName: checkoutString(
      shipping.last_name,
      "$.private.shipping_address.last_name",
    ),
    address1: checkoutString(
      shipping.address_1,
      "$.private.shipping_address.address_1",
    ),
    city: checkoutString(shipping.city, "$.private.shipping_address.city"),
    postalCode: checkoutString(
      shipping.postal_code,
      "$.private.shipping_address.postal_code",
    ),
    countryCode: checkoutString(
      shipping.country_code,
      "$.private.shipping_address.country_code",
    ),
  };
}
