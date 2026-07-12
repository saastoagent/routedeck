import "@testing-library/jest-dom/vitest";

import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { CheckoutPlacementSurface } from "../features/checkout/CheckoutPlacementSurface";

it("blocks automatic reconciliation when no order reference is available", () => {
  const dispatchAffordance = vi.fn(async () => {
    throw new Error("an unavailable recovery action must not dispatch");
  });

  render(
    <CheckoutPlacementSurface
      surface={{
        surface_id: "checkout.recovery",
        component: "checkout.recovery",
        props: [],
      }}
      slot="diagnostic"
      props={{
        state: "external_outcome_unknown",
        message: "The order outcome is uncertain; do not submit again.",
        correlation_id: "correlation-public-1",
      }}
      spec={{
        id: "checkout.recovery",
        component: "checkout.recovery",
        lifecycle: "stable",
        public_props_schema: {},
        affordances: [
          {
            id: "reconcile_order",
            event: "retry",
            operation: { id: "orders.reconcile" },
          },
        ],
      }}
      dispatchAffordance={dispatchAffordance}
    />,
  );

  expect(
    screen.getByText(
      "Automatic status checks are unavailable because this session has no verified order reference.",
    ),
  ).toBeVisible();
  expect(
    screen.queryByRole("button", { name: "Check order status" }),
  ).not.toBeInTheDocument();
  expect(dispatchAffordance).not.toHaveBeenCalled();
});
