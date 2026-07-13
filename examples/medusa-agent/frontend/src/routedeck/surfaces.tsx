import { defineRouteDeckSurfaceRegistry } from "@routedeck/react";

import { CartSummarySurface } from "../features/cart/CartSummarySurface";
import { ProductDetailSurface } from "../features/catalog/ProductDetailSurface";
import { ProductGridSurface } from "../features/catalog/ProductGridSurface";
import { ContactFormSurface } from "../features/checkout/ContactFormSurface";
import { CheckoutPlacementSurface } from "../features/checkout/CheckoutPlacementSurface";
import { OrderReviewSurface } from "../features/checkout/OrderReviewSurface";
import { PaymentMethodSurface } from "../features/checkout/PaymentMethodSurface";
import { ShippingOptionsSurface } from "../features/checkout/ShippingOptionsSurface";
import { OrderConfirmationSurface } from "../features/orders/OrderConfirmationSurface";

export const medusaRouteDeckSurfaces = defineRouteDeckSurfaceRegistry({
  "catalog.product_grid": ProductGridSurface,
  "catalog.product_detail": ProductDetailSurface,
  "cart.summary": CartSummarySurface,
  "checkout.contact_form": ContactFormSurface,
  "checkout.shipping_options": ShippingOptionsSurface,
  "checkout.payment_method": PaymentMethodSurface,
  "checkout.order_review": OrderReviewSurface,
  "checkout.review": CheckoutPlacementSurface,
  "checkout.recovery": CheckoutPlacementSurface,
  "orders.confirmation": OrderConfirmationSurface,
});
