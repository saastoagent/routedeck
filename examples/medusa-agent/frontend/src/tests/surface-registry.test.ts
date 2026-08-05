import { describe, expect, it } from "vitest";

import { medusaRouteDeckSurfaces } from "../routedeck/surfaces";

const DECLARED_STRUCTURAL_COMPONENTS = [
  "buyer.frame",
  "catalog.frame",
  "catalog.status",
  "catalog.error",
  "catalog.diagnostic",
  "cart.frame",
  "cart.status",
  "cart.error",
  "cart.diagnostic",
  "checkout.frame",
  "checkout.status",
  "checkout.error",
  "checkout.diagnostic",
  "orders.frame",
  "orders.status",
  "orders.error",
  "orders.diagnostic",
] as const;

describe("Medusa RouteDeck surface registry", () => {
  it("registers every structural component declared by the backend contract", () => {
    for (const component of DECLARED_STRUCTURAL_COMPONENTS) {
      expect(medusaRouteDeckSurfaces, component).toHaveProperty(component);
    }
  });
});
