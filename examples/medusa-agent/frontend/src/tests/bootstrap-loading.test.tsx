import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";

import { BootstrapLoadingShell } from "../app/BootstrapLoadingShell";

afterEach(cleanup);

it.each([
  ["storefront", "Loading storefront"],
  ["session", "Starting buyer session"],
  ["checkout", "Restoring checkout"],
  ["setup", "Finishing buyer setup"],
] as const)("renders the %s bootstrap phase", (phase, label) => {
  render(<BootstrapLoadingShell phase={phase} />);

  expect(screen.getByRole("status")).toHaveTextContent(label);
});
