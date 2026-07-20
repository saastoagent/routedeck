import type { JsonObject } from "@routedeck/core";
import { describe, expect, it } from "vitest";

import vectorsDocument from "../../../contracts/surface-props-parity.json";
import { decodeCartSummary } from "../features/cart/CartSummarySurface";
import { decodeProductDetail } from "../features/catalog/ProductDetailSurface";
import { decodeCatalogGrid } from "../features/catalog/ProductGridSurface";
import { decodeContactProjection } from "../features/checkout/contactFormModel";
import { decodeOrderReview } from "../features/checkout/OrderReviewSurface";
import { decodePaymentProjection } from "../features/checkout/PaymentMethodSurface";
import { decodeShippingProjection } from "../features/checkout/ShippingOptionsSurface";
import { decodeVerifiedOrder } from "../features/orders/OrderConfirmationSurface";

interface SurfaceParityVector {
  case_id: string;
  surface_id: keyof typeof decoders;
  payload: JsonObject;
  valid: boolean;
}

const decoders = {
  "catalog.product_grid": decodeCatalogGrid,
  "catalog.product_detail": decodeProductDetail,
  "cart.summary": decodeCartSummary,
  "checkout.contact_form": decodeContactProjection,
  "checkout.shipping_options": decodeShippingProjection,
  "checkout.payment_method": decodePaymentProjection,
  "checkout.order_review": decodeOrderReview,
  "orders.confirmation": decodeVerifiedOrder,
} as const;

describe("surface props parity", () => {
  const vectors = vectorsDocument.vectors as SurfaceParityVector[];

  it("covers every product surface decoder with valid and invalid payloads", () => {
    expect(new Set(vectors.map((vector) => vector.surface_id))).toEqual(
      new Set(Object.keys(decoders)),
    );
    for (const surfaceId of Object.keys(decoders)) {
      const expected = vectors
        .filter((vector) => vector.surface_id === surfaceId)
        .map((vector) => vector.valid);
      expect(new Set(expected), surfaceId).toEqual(new Set([true, false]));
    }
  });

  it.each(vectors)("$case_id ($surface_id)", (vector) => {
    const decode = decoders[vector.surface_id];
    const invoke = () => decode(vector.payload);
    if (vector.valid) {
      expect(invoke).not.toThrow();
    } else {
      expect(invoke).toThrow();
    }
  });
});
