import { expect, test } from "./support/fixtures";

test("@live-model moves RouteDeck from home to catalog through the real agent", async ({
  page,
}) => {
  test.setTimeout(180_000);
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Shop with Medusa", exact: true }),
  ).toBeVisible();

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
