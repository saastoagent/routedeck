import { expect, test } from "./support/fixtures";
import { writeMeasuredSseTrace } from "./support/release-evidence";

test("@scripted @scripted-agent drives catalog navigation through a model tool call", async ({
  page,
}, testInfo) => {
  test.skip(
    testInfo.project.name !== "desktop-chromium",
    "The bounded scripted model has one release scenario.",
  );
  expect(process.env.ROUTEDECK_MODEL_MODE).toBe("scripted-test-only");

  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Shop with Medusa", exact: true }),
  ).toBeVisible();

  const message = "Use the buyer tools to show me the available products.";
  await page
    .getByLabel("Message the buyer assistant", { exact: true })
    .fill(message);
  const chatResponse = page.waitForResponse((response) => {
    const request = response.request();
    return (
      request.method() === "POST" &&
      new URL(response.url()).pathname === "/api/routedeck/chat"
    );
  });
  await page.getByRole("button", { name: "Send", exact: true }).click();
  const measuredChatResponse = await chatResponse;
  expect(measuredChatResponse.ok()).toBe(true);

  await expect(
    page.getByRole("heading", { name: "Products", exact: true }),
  ).toBeVisible();
  await expect(page).toHaveURL(new URL("/products", page.url()).toString());
  await expect(
    page
      .locator(
        '[data-agent-message="assistant"][data-agent-message-status="finalized"]',
      )
      .filter({ hasText: "The available products are open." }),
  ).toHaveCount(1);
  await expect(page.locator("[data-agent-chat-error]")).toHaveCount(0);
  await writeMeasuredSseTrace(measuredChatResponse, testInfo);
});
