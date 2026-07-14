import {
  completeGuestCheckout,
  expectProduct,
  openCart,
  selectVariantAndAddToCart,
} from "./support/buyer-flow";
import { expect, test } from "./support/fixtures";
import { PRODUCT, buyerForProject } from "./support/test-data";

test("@user-story completes a hybrid agent-guided guest purchase", async ({
  page,
}, testInfo) => {
  test.setTimeout(240_000);
  const monitor = monitorRenderedJourney(page);
  const buyer = buyerForProject(testInfo.project.name);

  await page.goto("/");
  await expect(page.getByTestId("medusa-buyer-app")).toBeVisible();

  const message = "Browse the available products.";
  const chatResponse = page.waitForResponse((response) => {
    const request = response.request();
    return (
      request.method() === "POST" &&
      new URL(response.url()).pathname === "/api/routedeck/chat"
    );
  });
  await page
    .getByLabel("Message the buyer assistant", { exact: true })
    .fill(message);
  await page
    .getByLabel("Message the buyer assistant", { exact: true })
    .press("Enter");

  const chat = await chatResponse;
  expect(chat.ok(), "The agent chat request must succeed.").toBe(true);
  expect(
    chat.headers()["content-type"],
    "Product chat must stream an SSE response.",
  ).toContain("text/event-stream");
  await expect(
    page.getByRole("heading", { name: "Products", exact: true }),
  ).toBeVisible({ timeout: 150_000 });
  await expect(page).toHaveURL(new URL("/products", page.url()).toString());
  await page
    .getByRole("link", { name: PRODUCT.catalogLinkLabel, exact: true })
    .click();
  await expectProduct(page);
  await expect(
    page.locator(
      '[data-agent-message="assistant"][data-agent-message-status="finalized"]',
    ),
  ).toHaveCount(2, { timeout: 150_000 });
  await expect(
    page.locator(
      '[data-agent-message="assistant"][data-agent-message-status="streaming"]',
    ),
  ).toHaveCount(0);
  await selectVariantAndAddToCart(page);
  await openCart(page);

  const confirmationUrl = await completeGuestCheckout(page, buyer);
  expect(new URL(confirmationUrl).pathname).toMatch(
    /^\/orders\/[^/]+\/confirmation$/,
  );

  const report = monitor.report();
  expect(report.agent_chat_response_count).toBeGreaterThanOrEqual(1);
  expect(report.routedeck_session_response_count).toBeGreaterThanOrEqual(1);
  expect(report.routedeck_dispatch_response_count).toBeGreaterThanOrEqual(1);
  expect(report.routedeck_projection_response_count).toBeGreaterThanOrEqual(1);
  await testInfo.attach("hybrid-journey-monitoring.json", {
    body: Buffer.from(JSON.stringify(report, null, 2)),
    contentType: "application/json",
  });
});

interface HybridJourneyMonitoring {
  readonly agent_chat_response_count: number;
  readonly routedeck_session_response_count: number;
  readonly routedeck_dispatch_response_count: number;
  readonly routedeck_projection_response_count: number;
  readonly successful_paths: readonly string[];
}

function monitorRenderedJourney(
  page: import("@playwright/test").Page,
): { report(): HybridJourneyMonitoring } {
  let agentChatResponseCount = 0;
  let routeDeckSessionResponseCount = 0;
  let routeDeckDispatchResponseCount = 0;
  let routeDeckProjectionResponseCount = 0;
  const successfulPaths = new Set<string>();

  page.on("response", (response) => {
    if (!response.ok()) return;
    const url = new URL(response.url());
    const path = url.pathname;
    if (path === "/api/routedeck/chat") {
      agentChatResponseCount += 1;
      successfulPaths.add(path);
      return;
    }
    if (path === "/api/routedeck/sessions") {
      routeDeckSessionResponseCount += 1;
      successfulPaths.add(path);
      return;
    }
    if (path === "/api/routedeck/dispatch") {
      routeDeckDispatchResponseCount += 1;
      successfulPaths.add(path);
      return;
    }
    if (
      path === "/api/routedeck/session" ||
      path === "/api/routedeck/events" ||
      path === "/api/routedeck/navigation"
    ) {
      routeDeckProjectionResponseCount += 1;
      successfulPaths.add(path);
    }
  });

  return {
    report: () => ({
      agent_chat_response_count: agentChatResponseCount,
      routedeck_session_response_count: routeDeckSessionResponseCount,
      routedeck_dispatch_response_count: routeDeckDispatchResponseCount,
      routedeck_projection_response_count: routeDeckProjectionResponseCount,
      successful_paths: [...successfulPaths].sort(),
    }),
  };
}
