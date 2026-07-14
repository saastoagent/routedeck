import { expect, test } from "./support/fixtures";

test("@live-model greets, streams a conversational hello, and stays home", async ({
  page,
}) => {
  test.setTimeout(180_000);
  await page.goto("/");
  await expect(page.getByTestId("medusa-buyer-app")).toBeVisible();

  const assistantMessages = page.locator(
    '[data-agent-message="assistant"][data-agent-message-status="finalized"]',
  );
  await expect(assistantMessages).toHaveCount(1);
  await expect(assistantMessages.first().locator("p")).toContainText(/^Hi\b/i);
  await installChatTimeline(page);

  const message = "Hello";
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
  await page
    .getByLabel("Message the buyer assistant", { exact: true })
    .press("Enter");

  await expect(
    page.locator('[data-agent-message="user"]').filter({ hasText: message }),
  ).toHaveCount(1);
  await expect(
    page.getByRole("status", { name: "Buyer assistant is thinking" }),
  ).toBeVisible();
  expect((await chatResponse).ok()).toBe(true);
  await expect(assistantMessages).toHaveCount(2, { timeout: 150_000 });
  await expect(
    page.getByRole("status", { name: "Buyer assistant is thinking" }),
  ).toHaveCount(0);

  const timeline = await page.evaluate(
    () =>
      (
        window as unknown as Window & {
          __routedeckChatTimeline: string[];
        }
      ).__routedeckChatTimeline,
  );
  expect(timeline).toContain("thinking");
  expect(timeline).toContain("streaming");
  expect(timeline).toContain("finalized");
  expect(timeline.indexOf("thinking")).toBeLessThan(
    timeline.indexOf("streaming"),
  );
  expect(timeline.indexOf("streaming")).toBeLessThan(
    timeline.indexOf("finalized"),
  );
  await expect(page).toHaveURL("http://127.0.0.1:5198/");
  await expect(
    page.getByRole("heading", { name: "Products", exact: true }),
  ).toHaveCount(0);
  await expect(page.locator("[data-agent-chat-error]")).toHaveCount(0);
});

test("@live-model moves RouteDeck from home to catalog through the real agent", async ({
  page,
}) => {
  test.setTimeout(180_000);
  await page.goto("/");
  await expect(page.getByTestId("medusa-buyer-app")).toBeVisible();

  const message = "Browse the available products.";
  await page
    .getByLabel("Message the buyer assistant", { exact: true })
    .fill(message);
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(
    page.locator('[data-agent-message="user"]').filter({ hasText: message }),
  ).toHaveCount(1);

  const products = page.getByRole("heading", {
    name: "Products",
    exact: true,
  });
  const chatFailure = page.locator("[data-agent-chat-error]").first();
  await Promise.race([
    products.waitFor({ state: "visible", timeout: 150_000 }),
    chatFailure.waitFor({ state: "visible", timeout: 150_000 }).then(() => {
      throw new Error("The live buyer agent returned a visible chat failure.");
    }),
  ]);
  await expect(page).toHaveURL(new URL("/products", page.url()).toString());
  await expect(
    page.locator(
      '[data-agent-message="assistant"][data-agent-message-status="finalized"]',
    ),
  ).toHaveCount(1);
  await expect(page.locator("[data-agent-chat-error]")).toHaveCount(0);
});

async function installChatTimeline(
  page: import("@playwright/test").Page,
): Promise<void> {
  await page.evaluate(() => {
    const timeline: string[] = [];
    Object.defineProperty(window, "__routedeckChatTimeline", {
      configurable: true,
      value: timeline,
    });
    const record = () => {
      if (
        !timeline.includes("thinking") &&
        document.querySelector(
          '[data-agent-message="assistant"][data-agent-message-status="thinking"]',
        )
      ) {
        timeline.push("thinking");
      }
      if (
        !timeline.includes("streaming") &&
        document.querySelector(
          '[data-agent-message="assistant"][data-agent-message-status="streaming"]',
        )
      ) {
        timeline.push("streaming");
      }
      if (
        !timeline.includes("finalized") &&
        document.querySelectorAll(
          '[data-agent-message="assistant"][data-agent-message-status="finalized"]',
        ).length >= 2
      ) {
        timeline.push("finalized");
      }
    };
    new MutationObserver(record).observe(document.body, {
      attributes: true,
      childList: true,
      characterData: true,
      subtree: true,
    });
    record();
  });
}
