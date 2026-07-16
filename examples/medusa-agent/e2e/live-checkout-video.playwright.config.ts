import { fileURLToPath } from "node:url";
import path from "node:path";

import { defineConfig } from "@playwright/test";

const artifactRoot = process.env.ROUTEDECK_E2E_ARTIFACTS;
if (artifactRoot === undefined || artifactRoot.trim().length === 0) {
  throw new Error("ROUTEDECK_E2E_ARTIFACTS is required.");
}
if (!path.isAbsolute(artifactRoot)) {
  throw new Error("ROUTEDECK_E2E_ARTIFACTS must be an absolute path.");
}

const e2eRoot = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  testDir: e2eRoot,
  testMatch: "human-checkout-flow.spec.ts",
  outputDir: path.join(artifactRoot, "raw-results"),
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: true,
  timeout: 420_000,
  expect: {
    timeout: 20_000,
  },
  reporter: [
    ["line"],
    ["json", { outputFile: path.join(artifactRoot, "playwright-report.json") }],
  ],
  use: {
    baseURL:
      process.env.ROUTEDECK_E2E_BASE_URL ?? "http://127.0.0.1:5198",
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1,
    serviceWorkers: "block",
    actionTimeout: 20_000,
    navigationTimeout: 30_000,
    video: {
      mode: "on",
      size: { width: 1920, height: 1080 },
    },
    screenshot: "on",
    trace: "on",
  },
  projects: [
    {
      name: "desktop-chromium",
      use: {
        browserName: "chromium",
      },
    },
  ],
});
