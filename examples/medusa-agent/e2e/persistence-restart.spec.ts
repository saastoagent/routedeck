import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

import { expect, test } from "./support/fixtures";

test("@persistence-restart restores the exact confirmation after agent API restart", async ({
  page,
}) => {
  const bundleRoot = requiredEnvironment("ROUTEDECK_RELEASE_BUNDLE");
  const rawDir = requiredEnvironment("ROUTEDECK_RELEASE_RAW_DIR");
  const input = await readObject(path.join(rawDir, "persistence-input.json"));
  const restart = await readObject(path.join(rawDir, "restart-observed.json"));
  const confirmationUrl = requiredString(input.confirmation_url, "confirmation_url");
  const runId = requiredString(input.run_id, "run_id");
  expect(restart.run_id).toBe(runId);
  expect(restart.agent_api_restart_command_status).toBe("pass");
  expect(restart.post_restart_health_status).toBe(200);
  expect(input.pre_restart_confirmation_observed).toBe(true);

  const cookiesBeforeNavigation = await page.context().cookies();
  const sessionCookieRestored = cookiesBeforeNavigation.some(
    (cookie) => cookie.name === "routedeck_guest" && cookie.value.length > 0,
  );
  expect(sessionCookieRestored).toBe(true);

  await page.goto(confirmationUrl);
  await expect(
    page.getByRole("heading", {
      name: "Order confirmed",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("complementary", {
        name: "RouteDeck session status",
        exact: true,
      })
      .getByText("live", { exact: true }),
  ).toBeVisible();
  const expectedHandle = new URL(confirmationUrl).pathname
    .split("/")
    .filter(Boolean)[1];
  const observedHandle = await page
    .locator("section[data-confirmation]")
    .getAttribute("data-confirmation");
  const confirmationHandleMatch =
    expectedHandle !== undefined && observedHandle === expectedHandle;
  expect(confirmationHandleMatch).toBe(true);

  const runtimeDir = path.join(bundleRoot, "runtime");
  await mkdir(runtimeDir, { recursive: true });
  await writeFile(
    path.join(runtimeDir, "persistence-restart.json"),
    `${JSON.stringify(
      {
        schema_version: 1,
        status: "pass",
        source: "playwright_confirmation_probe_after_measured_agent_api_restart",
        run_id: runId,
        route_template: "/orders/{confirmation_handle}/confirmation",
        pre_restart_confirmation_observed: true,
        post_restart_confirmation_observed: true,
        session_cookie_restored: sessionCookieRestored,
        confirmation_handle_match: confirmationHandleMatch,
        post_restart_health_status: restart.post_restart_health_status,
      },
      null,
      2,
    )}\n`,
    "utf8",
  );
});

function requiredEnvironment(name: string): string {
  const value = process.env[name];
  if (value === undefined || value.trim().length === 0) {
    throw new Error(`${name} is required.`);
  }
  return value;
}

async function readObject(file: string): Promise<Record<string, unknown>> {
  const value: unknown = JSON.parse(await readFile(file, "utf8"));
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`${file} must contain a JSON object.`);
  }
  return value as Record<string, unknown>;
}

function requiredString(value: unknown, label: string): string {
  if (typeof value !== "string" || value.length === 0) {
    throw new Error(`${label} must be a non-empty string.`);
  }
  return value;
}
