import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";

import { BootstrapLoadingShell } from "../app/BootstrapLoadingShell";

afterEach(cleanup);

it("renders one neutral bootstrap message", () => {
  render(<BootstrapLoadingShell />);

  const status = screen.getByRole("status");
  expect(status).toHaveTextContent("Medusa Agent");
  expect(status).toHaveTextContent("Preparing your shopping experience");
  expect(status).not.toHaveTextContent("Starting buyer session");
  expect(status).not.toHaveTextContent("Restoring checkout");
  expect(status).not.toHaveTextContent("Finishing buyer setup");
});
