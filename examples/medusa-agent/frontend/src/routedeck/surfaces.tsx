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
import { StructuralSurface } from "./StructuralSurface";

export const medusaRouteDeckSurfaces = defineRouteDeckSurfaceRegistry({
  "buyer.frame": StructuralSurface,
  "catalog.frame": StructuralSurface,
  "catalog.product_grid": ProductGridSurface,
  "catalog.product_detail": ProductDetailSurface,
  "catalog.status": StructuralSurface,
  "catalog.error": StructuralSurface,
  "catalog.diagnostic": StructuralSurface,
  "cart.frame": StructuralSurface,
  "cart.summary": CartSummarySurface,
  "cart.status": StructuralSurface,
  "cart.error": StructuralSurface,
  "cart.diagnostic": StructuralSurface,
  "checkout.frame": StructuralSurface,
  "checkout.contact_form": ContactFormSurface,
  "checkout.shipping_options": ShippingOptionsSurface,
  "checkout.payment_method": PaymentMethodSurface,
  "checkout.order_review": OrderReviewSurface,
  "checkout.review": CheckoutPlacementSurface,
  "checkout.status": StructuralSurface,
  "checkout.error": StructuralSurface,
  "checkout.recovery": CheckoutPlacementSurface,
  "checkout.diagnostic": StructuralSurface,
  "orders.frame": StructuralSurface,
  "orders.confirmation": OrderConfirmationSurface,
  "orders.status": StructuralSurface,
  "orders.error": StructuralSurface,
  "orders.diagnostic": StructuralSurface,
});
