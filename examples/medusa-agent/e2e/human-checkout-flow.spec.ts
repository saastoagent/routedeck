import type { Page } from "@playwright/test";

import {
  completeGuestCheckout,
  expectCart,
  expectProduct,
  selectVariantAndAddToCart,
} from "./support/buyer-flow";
import { expect, test } from "./support/fixtures";
import { PRODUCT, buyerForProject } from "./support/test-data";

const ROUTEDECK_CHAT_PATH = "/api/routedeck/chat";
const LOCAL_APP_ORIGIN = "http://127.0.0.1:5198";
const FINALIZED_ASSISTANT_SELECTOR =
  '[data-agent-message="assistant"][data-agent-message-status="finalized"]';
const CHAT_ERROR_SELECTOR = "[data-agent-chat-error]";
const CHAT_TIMEOUT_MS = 150_000;

test("@human-checkout completes one live conversational hybrid purchase", async ({
  browserSafety,
  page,
}, testInfo) => {
  expect(process.env.ROUTEDECK_MODEL_MODE).toBe("live");
  expect(
    testInfo.project.use.baseURL,
    "The recorded human checkout must target the approved local RouteDeck stack.",
  ).toBe(LOCAL_APP_ORIGIN);
  test.setTimeout(360_000);
  const buyer = buyerForProject(testInfo.project.name);

  await page.goto("/");
  await expect(page.getByTestId("medusa-buyer-app")).toBeVisible();
  await expect(page.locator(FINALIZED_ASSISTANT_SELECTOR)).toHaveCount(1, {
    timeout: CHAT_TIMEOUT_MS,
  });

  await sendCasualChat(
    page,
    "Hey — I'm looking for a black tee. Can you show me what you've got?",
    "/products",
  );

  await page
    .getByRole("link", { name: PRODUCT.catalogLinkLabel, exact: true })
    .click();
  await expectProduct(page);
  await selectVariantAndAddToCart(page);

  await sendCasualChat(
    page,
    "Nice, that works for me. Can you take me to my cart?",
    "/cart",
  );
  await expectCart(page);

  const confirmationUrl = await completeGuestCheckout(page, buyer);
  expect(new URL(confirmationUrl).pathname).toMatch(
    /^\/orders\/[^/]+\/confirmation$/,
  );
  await expect(
    page.getByRole("heading", { name: "Order confirmed", exact: true }),
  ).toBeVisible();
  browserSafety.assertClean();
});

async function sendCasualChat(
  page: Page,
  message: string,
  expectedPath: string,
): Promise<void> {
  const finalizedAssistant = page.locator(FINALIZED_ASSISTANT_SELECTOR);
  const finalizedCount = await finalizedAssistant.count();
  const chatError = page.locator(CHAT_ERROR_SELECTOR).first();
  const composer = page.getByLabel("Message the buyer assistant", {
    exact: true,
  });

  await composer.click();
  await composer.pressSequentially(message, { delay: 30 });
  const chatResponse = page.waitForResponse(
    (response) => {
      const request = response.request();
      return (
        request.method() === "POST" &&
        new URL(response.url()).pathname === ROUTEDECK_CHAT_PATH
      );
    },
    { timeout: CHAT_TIMEOUT_MS },
  );
  await composer.press("Enter");

  const response = await chatResponse;
  expect(response.ok(), "The live RouteDeck chat request must succeed.").toBe(
    true,
  );
  expect(
    response.headers()["content-type"],
    "The live RouteDeck chat response must use SSE.",
  ).toContain("text/event-stream");

  await expect
    .poll(
      async () => {
        if (await chatError.isVisible()) {
          throw new Error(
            `The live buyer agent returned a visible chat failure: ${
              (await chatError.textContent()) ?? "unknown error"
            }`,
          );
        }
        return {
          assistantCount: await finalizedAssistant.count(),
          path: new URL(page.url()).pathname,
        };
      },
      {
        message: `The live agent must finalize its reply and navigate to ${expectedPath}.`,
        timeout: CHAT_TIMEOUT_MS,
      },
    )
    .toEqual({
      assistantCount: finalizedCount + 1,
      path: expectedPath,
    });
  await expect(page.locator(CHAT_ERROR_SELECTOR)).toHaveCount(0);
}
