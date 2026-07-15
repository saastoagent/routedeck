import { fileURLToPath } from "node:url";

import {
  defineConfig,
  devices,
  type ReporterDescription,
} from "@playwright/test";

const e2eRoot = fileURLToPath(new URL(".", import.meta.url));
const baseURL =
  process.env.ROUTEDECK_E2E_BASE_URL ?? "http://127.0.0.1:5198";
const reporter = releaseReporter();

export default defineConfig({
  testDir: e2eRoot,
  outputDir: fileURLToPath(new URL("./test-results", import.meta.url)),
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: true,
  timeout: 120_000,
  expect: {
    timeout: 20_000,
  },
  reporter,
  use: {
    baseURL,
    ...(process.env.ROUTEDECK_PERSISTENCE_STORAGE_STATE === undefined
      ? {}
      : {
          storageState: process.env.ROUTEDECK_PERSISTENCE_STORAGE_STATE,
        }),
    actionTimeout: 20_000,
    navigationTimeout: 30_000,
    serviceWorkers: "block",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: videoMode(),
  },
  projects: [
    {
      name: "desktop-chromium",
      use: {
        ...devices["Desktop Chrome"],
      },
    },
    {
      name: "mobile-chromium",
      use: {
        ...devices["Pixel 7"],
      },
    },
  ],
});

function videoMode(): "on" | "retain-on-failure" {
  const value = process.env.ROUTEDECK_E2E_VIDEO;
  if (value === undefined) return "retain-on-failure";
  if (value !== "on") {
    throw new Error("ROUTEDECK_E2E_VIDEO must be 'on' when set.");
  }
  return value;
}

function releaseReporter(): ReporterDescription[] {
  const bundleRoot = process.env.ROUTEDECK_RELEASE_BUNDLE;
  if (bundleRoot === undefined) return [["line"]];
  if (bundleRoot.trim().length === 0) {
    throw new Error("ROUTEDECK_RELEASE_BUNDLE must not be empty when set.");
  }
  const reportName = process.env.ROUTEDECK_E2E_REPORT_NAME;
  if (
    reportName !== "scripted" &&
    reportName !== "persistence" &&
    reportName !== "live-model"
  ) {
    throw new Error(
      "ROUTEDECK_E2E_REPORT_NAME must be scripted, persistence, or live-model for release runs.",
    );
  }
  return [
    ["line"],
    [fileURLToPath(new URL("./support/release-reporter.ts", import.meta.url))],
  ];
}
