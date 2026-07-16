import type { Page } from "@playwright/test";

import {
  completeGuestCheckout,
  expectCart,
  expectProduct,
  selectVariantAndAddToCart,
  type CheckoutFlowStage,
} from "./support/buyer-flow";
import { expect, test } from "./support/fixtures";
import { PRODUCT, buyerForProject } from "./support/test-data";

const ROUTEDECK_CHAT_PATH = "/api/routedeck/chat";
const LOCAL_APP_ORIGIN = "http://127.0.0.1:5198";
const FINALIZED_ASSISTANT_SELECTOR =
  '[data-agent-message="assistant"][data-agent-message-status="finalized"]';
const CHAT_ERROR_SELECTOR = "[data-agent-chat-error]";
const CHAT_TIMEOUT_MS = 150_000;
const NAVGRAPH_READING_PAUSE_MS = 650;

const CHECKOUT_NODES: Readonly<Record<CheckoutFlowStage, string>> = {
  contact: "checkout.contact",
  delivery: "checkout.delivery",
  payment: "checkout.payment",
  review: "checkout.review",
  approval: "checkout.review",
  confirmation: "orders.confirmation",
};

test("@human-checkout completes one curious conversational hybrid purchase with visible navigation proof", async ({
  browserSafety,
  page,
}, testInfo) => {
  expect(process.env.ROUTEDECK_MODEL_MODE).toBe("live");
  expect(
    testInfo.project.use.baseURL,
    "The recorded human checkout must target the approved local RouteDeck stack.",
  ).toBe(LOCAL_APP_ORIGIN);
  test.setTimeout(420_000);
  const buyer = buyerForProject(testInfo.project.name);

  await page.goto("/");
  await expect(page.getByTestId("medusa-buyer-app")).toBeVisible();
  await expect(page.locator(FINALIZED_ASSISTANT_SELECTOR)).toHaveCount(1, {
    timeout: CHAT_TIMEOUT_MS,
  });
  await showCurrentNavgraphNode(page, "buyer.home");
  await closeNavgraph(page);

  await sendCasualChat(
    page,
    "Hey! I'm new here. What can I actually shop for on this site?",
    "/products",
  );
  await expect(
    page.getByRole("heading", { name: "Products", exact: true }),
  ).toBeVisible();
  await showCurrentNavgraphNode(page, "catalog.products");
  await closeNavgraph(page);

  const productLink = page.getByRole("link", {
    name: PRODUCT.catalogLinkLabel,
    exact: true,
  });
  const productHref = await productLink.getAttribute("href");
  expect(productHref).not.toBeNull();
  const productDeepLink = new URL(productHref!, page.url()).toString();

  await page.goto(productDeepLink);
  await expectProduct(page);
  await showCurrentNavgraphNode(page, "catalog.product");
  await closeNavgraph(page);

  await page.reload({ waitUntil: "domcontentloaded" });
  expect(page.url()).toBe(productDeepLink);
  await expectProduct(page);
  await showCurrentNavgraphNode(page, "catalog.product");
  await closeNavgraph(page);

  await sendCasualChat(
    page,
    "This one caught my eye, but I'm not settled yet. What size and color options does it come in?",
    PRODUCT.path,
  );
  await selectVariantAndAddToCart(page, ["2", "1"]);

  await sendCasualChat(
    page,
    "Actually, let's keep it to one. Please take me to my cart.",
    "/cart",
  );
  await expectCart(page);
  await showCurrentNavgraphNode(page, "cart.summary");
  await closeNavgraph(page);

  let deliveryDeepLink: string | null = null;
  let deliveryResumeHandle: string | null = null;
  const confirmationUrl = await completeGuestCheckout(
    page,
    buyer,
    undefined,
    {
      async onStage(stage, checkoutPage) {
        await showCurrentNavgraphNode(checkoutPage, CHECKOUT_NODES[stage]);
        await closeNavgraph(checkoutPage);

        if (stage !== "delivery" || deliveryDeepLink !== null) return;

        const deliveryUrl = new URL(checkoutPage.url());
        expect(deliveryUrl.pathname).toBe("/checkout/delivery");
        deliveryResumeHandle = deliveryUrl.searchParams.get("resume_handle");
        expect(deliveryResumeHandle).toBeTruthy();
        deliveryDeepLink = deliveryUrl.toString();

        await checkoutPage.reload({ waitUntil: "domcontentloaded" });
        expect(checkoutPage.url()).toBe(deliveryDeepLink);
        await expect(
          checkoutPage.getByRole("heading", {
            name: "Delivery options",
            exact: true,
          }),
        ).toBeVisible();
        expect(new URL(checkoutPage.url()).searchParams.get("resume_handle")).toBe(
          deliveryResumeHandle,
        );
        await showCurrentNavgraphNode(checkoutPage, "checkout.delivery");
        await closeNavgraph(checkoutPage);
      },
    },
  );

  expect(deliveryDeepLink).not.toBeNull();
  expect(deliveryResumeHandle).not.toBeNull();
  expect(new URL(confirmationUrl).pathname).toMatch(
    /^\/orders\/[^/]+\/confirmation$/,
  );
  await expect(
    page.getByRole("heading", { name: "Order confirmed", exact: true }),
  ).toBeVisible();
  await showCurrentNavgraphNode(page, "orders.confirmation");
  await closeNavgraph(page);

  const confirmationHandle = await page
    .locator("section[data-confirmation]")
    .getAttribute("data-confirmation");
  expect(confirmationHandle).toBeTruthy();
  await page.reload({ waitUntil: "domcontentloaded" });
  expect(page.url()).toBe(confirmationUrl);
  await expect(page.locator("section[data-confirmation]")).toHaveAttribute(
    "data-confirmation",
    confirmationHandle!,
  );
  await showCurrentNavgraphNode(page, "orders.confirmation");

  await expect(
    page.locator(`${FINALIZED_ASSISTANT_SELECTOR} > article > .assistant-markdown`),
  ).toHaveCount(await page.locator(FINALIZED_ASSISTANT_SELECTOR).count());
  await expect(
    page.locator(`${FINALIZED_ASSISTANT_SELECTOR} > article > p`),
  ).toHaveCount(0);
  for (const content of await page
    .locator(FINALIZED_ASSISTANT_SELECTOR)
    .allTextContents()) {
    expect(content).not.toMatch(/(?:tool_call|function_call|"arguments"\s*:)/i);
  }
  browserSafety.assertClean();
});

async function showCurrentNavgraphNode(
  page: Page,
  nodeId: string,
): Promise<void> {
  const navgraph = page.getByRole("complementary", {
    name: "Navgraph",
    exact: true,
  });
  const open = page.getByRole("button", { name: "Open Navgraph", exact: true });

  if (await open.isVisible()) {
    await open.click();
  }

  await expect(
    navgraph.getByRole("button", { name: "Close Navgraph", exact: true }),
  ).toHaveAttribute("aria-expanded", "true");
  await expect(navgraph.locator(".navgraph-session-facts")).toContainText(nodeId);
  await expect(
    navgraph.locator(
      `[data-routedeck-navgraph-node="${nodeId}"][data-node-tone="current"]`,
    ),
  ).toHaveCount(1);
  await page.waitForTimeout(NAVGRAPH_READING_PAUSE_MS);
}

async function closeNavgraph(page: Page): Promise<void> {
  const close = page.getByRole("button", {
    name: "Close Navgraph",
    exact: true,
  });
  if (await close.isVisible()) {
    await close.click();
  }
}

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
