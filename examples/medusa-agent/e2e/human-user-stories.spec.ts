import type { Locator, Page, Request, TestInfo } from "@playwright/test";

import { expect, test, type BrowserSafety } from "./support/fixtures";
import {
  HumanStoryRecorder,
  addSelectedVariant,
  expectRouteDeckLive,
  humanBuyer,
  openCartFromSurface,
  openVisibleProduct,
  selectVisibleInStockVariant,
  sendHumanChat,
  visibleCatalogProducts,
  waitForSuccessfulPost,
  type HumanStoryId,
  type RenderedProduct,
} from "./support/human-story";

const LOCAL_APP_ORIGIN = "http://127.0.0.1:5198";
const FINALIZED_ASSISTANT_SELECTOR =
  '[data-agent-message="assistant"][data-agent-message-status="finalized"]';

test("US-01 Curious Newcomer", async ({ browserSafety, page }, testInfo) => {
  await runRecordedStory(
    "US-01",
    "Curious Newcomer",
    page,
    browserSafety,
    testInfo,
    async (recorder) => {
      await sendHumanChat(page, recorder, "Hey, I just landed here. What is this?");
      await sendHumanChat(
        page,
        recorder,
        "Okay, what can you actually help me do?",
      );
      await sendHumanChat(
        page,
        recorder,
        "Cool. Show me what you have.",
        "/products",
      );
      await expectCatalog(page);
      await visibleCatalogProducts(page);
      await recorder.capture("catalog");
    },
  );
});

test("US-02 Goal-Led Discovery and Clarification", async (
  { browserSafety, page },
  testInfo,
) => {
  await runRecordedStory(
    "US-02",
    "Goal-Led Discovery and Clarification",
    page,
    browserSafety,
    testInfo,
    async (recorder) => {
      await sendHumanChat(
        page,
        recorder,
        "I'm after something comfortable for a relaxed weekend, but I'm not sure what. Can you help me narrow it down?",
      );
      if (!(await isCatalogVisible(page))) {
        await sendHumanChat(
          page,
          recorder,
          "Could you show me the available options?",
          "/products",
        );
      }
      await expectCatalog(page);
      const products = await visibleCatalogProducts(page);
      const chosen = products[0]!;
      await openVisibleProduct(page, recorder, chosen);
      const productPath = new URL(page.url()).pathname;
      await sendHumanChat(
        page,
        recorder,
        `I can see the options for ${chosen.title} now. What should I consider when choosing between them?`,
        productPath,
      );
      await expect(
        page.getByRole("heading", { name: chosen.title, exact: true }),
      ).toBeVisible();
      await recorder.capture("clarification");
    },
  );
});

test("US-03 Shopper Changes Their Mind", async (
  { browserSafety, page },
  testInfo,
) => {
  await runRecordedStory(
    "US-03",
    "Shopper Changes Their Mind",
    page,
    browserSafety,
    testInfo,
    async (recorder) => {
      await sendHumanChat(
        page,
        recorder,
        "I'm just browsing. Show me what's available.",
        "/products",
      );
      await expectCatalog(page);
      const initialProducts = await visibleCatalogProducts(page);
      expect(initialProducts.length).toBeGreaterThanOrEqual(2);
      const first = initialProducts[0]!;
      await openVisibleProduct(page, recorder, first);
      await sendHumanChat(
        page,
        recorder,
        "I'm not sure this is the one. Can I see the other products again?",
        "/products",
      );
      await expectCatalog(page);
      const returnedProducts = await visibleCatalogProducts(page);
      const second = returnedProducts.find(
        (product) => product.handle !== first.handle,
      );
      expect(second, "The returned catalog must expose a different product.").toBeDefined();
      await openVisibleProduct(page, recorder, second!);
      await selectVisibleInStockVariant(page, recorder);
      await addSelectedVariant(page);
      await openCartFromSurface(page);
      await expectCartContainsOnly(page, second!);
      await recorder.capture("second-choice-cart");
    },
  );
});

test("US-04 Hybrid Cart Management", async (
  { browserSafety, page },
  testInfo,
) => {
  await runRecordedStory(
    "US-04",
    "Hybrid Cart Management",
    page,
    browserSafety,
    testInfo,
    async (recorder) => {
      await sendHumanChat(
        page,
        recorder,
        "I'd like to browse before deciding. What do you have?",
        "/products",
      );
      await expectCatalog(page);
      const product = (await visibleCatalogProducts(page))[0]!;
      await openVisibleProduct(page, recorder, product);
      await selectVisibleInStockVariant(page, recorder);
      await addSelectedVariant(page);
      await openCartFromSurface(page);
      const line = page.locator("[data-cart-line]");
      await expect(line).toHaveCount(1);

      const increase = line.locator('button[aria-label^="Increase quantity of "]');
      await clickCartMutation(page, increase);
      await expect(line.locator("output")).toHaveText("2");
      const assistant = await sendHumanChat(
        page,
        recorder,
        "What do I have in my cart right now?",
        "/cart",
      );
      recorder.record("assertion", {
        name: "cart_answer_for_manual_review",
        rendered_product: product.title,
        rendered_quantity: 2,
        assistant_answer: assistant,
      });

      const decrease = line.locator('button[aria-label^="Decrease quantity of "]');
      await clickCartMutation(page, decrease);
      await expect(line.locator("output")).toHaveText("1");
      await clickCartMutation(
        page,
        line.getByRole("button", { name: "Remove", exact: true }),
      );
      await expect(page.locator("[data-cart-line]")).toHaveCount(0);
      await expect(page.getByText("Your cart is empty.", { exact: true })).toBeVisible();
      await sendHumanChat(
        page,
        recorder,
        "I'd like to keep looking. Take me back to the products.",
        "/products",
      );
      await expectCatalog(page);
      await recorder.capture("returned-to-products");
    },
  );
});

test("US-05 Thoughtful Full Checkout", async (
  { browserSafety, page },
  testInfo,
) => {
  await runRecordedStory(
    "US-05",
    "Thoughtful Full Checkout",
    page,
    browserSafety,
    testInfo,
    async (recorder) => {
      await sendHumanChat(
        page,
        recorder,
        "Can you help me find something simple and affordable?",
      );
      if (!(await isCatalogVisible(page))) {
        await sendHumanChat(
          page,
          recorder,
          "Show me the options so I can decide.",
          "/products",
        );
      }
      await expectCatalog(page);
      const product = (await visibleCatalogProducts(page))[0]!;
      await openVisibleProduct(page, recorder, product);
      const productPath = new URL(page.url()).pathname;
      await sendHumanChat(
        page,
        recorder,
        `I'm looking at ${product.title}. What should I know before choosing an option?`,
        productPath,
      );
      await selectVisibleInStockVariant(page, recorder);
      await addSelectedVariant(page);
      await sendHumanChat(
        page,
        recorder,
        "This looks good. Can you take me to my cart?",
        "/cart",
      );
      await expectCartContainsOnly(page, product);
      await completeThoughtfulCheckout(page, recorder);
    },
  );
});

async function runRecordedStory(
  storyId: HumanStoryId,
  title: string,
  page: Page,
  browserSafety: BrowserSafety,
  testInfo: TestInfo,
  body: (recorder: HumanStoryRecorder) => Promise<void>,
): Promise<void> {
  expect(process.env.ROUTEDECK_MODEL_MODE).toBe("live");
  expect(testInfo.project.use.baseURL).toBe(LOCAL_APP_ORIGIN);
  const recorder = new HumanStoryRecorder(storyId, title, page);
  let failure: unknown;
  try {
    await page.goto("/");
    await expect(page.getByTestId("medusa-buyer-app")).toBeVisible();
    await expect(page.locator(FINALIZED_ASSISTANT_SELECTOR)).toHaveCount(1, {
      timeout: 150_000,
    });
    const viewport = await page.evaluate(() => ({
      width: window.innerWidth,
      height: window.innerHeight,
    }));
    expect(viewport).toEqual({ width: 1920, height: 1080 });
    recorder.record("assertion", {
      name: "viewport",
      width: viewport.width,
      height: viewport.height,
    });
    await expectRouteDeckLive(page);
    await recorder.capture("start");
    await page.waitForTimeout(1_000);
    await body(recorder);
    browserSafety.assertClean();
    recorder.record("assertion", { name: "browser_safety", status: "clean" });
    await recorder.finalize("passed");
  } catch (caught) {
    failure = caught;
    recorder.record("assertion", {
      name: "story_failure",
      message: caught instanceof Error ? caught.message : String(caught),
    });
    try {
      await recorder.capture("failure");
    } catch {
      // Evidence JSON remains mandatory even if the page can no longer render.
    }
    await recorder.finalize("failed", caught);
  }
  if (failure !== undefined) throw failure;
}

async function expectCatalog(page: Page): Promise<void> {
  await expect(
    page.getByRole("heading", { name: "Products", exact: true }),
  ).toBeVisible();
  await expect(page).toHaveURL(new URL("/products", page.url()).toString());
  await expectRouteDeckLive(page);
}

async function isCatalogVisible(page: Page): Promise<boolean> {
  return page
    .getByRole("heading", { name: "Products", exact: true })
    .isVisible();
}

async function expectCartContainsOnly(
  page: Page,
  product: RenderedProduct,
): Promise<void> {
  await expect(
    page.getByRole("heading", { name: "Your cart", exact: true }),
  ).toBeVisible();
  const lines = page.locator("[data-cart-line]");
  await expect(lines).toHaveCount(1);
  await expect(lines.getByText(product.title, { exact: true })).toBeVisible();
  await expectRouteDeckLive(page);
}

async function clickCartMutation(page: Page, control: Locator): Promise<void> {
  await expect(control).toHaveCount(1);
  const response = waitForSuccessfulPost(page, "/api/routedeck/dispatch");
  await control.click();
  await response;
  await page.waitForTimeout(900);
}

async function completeThoughtfulCheckout(
  page: Page,
  recorder: HumanStoryRecorder,
): Promise<void> {
  const buyer = humanBuyer("US-05");
  const acceptRequests: Request[] = [];
  const rejectRequests: Request[] = [];
  const trackReviews = (request: Request) => {
    const path = new URL(request.url()).pathname;
    if (request.method() !== "POST") return;
    if (/^\/api\/routedeck\/reviews\/[^/]+\/accept$/.test(path)) {
      acceptRequests.push(request);
    }
    if (/^\/api\/routedeck\/reviews\/[^/]+\/reject$/.test(path)) {
      rejectRequests.push(request);
    }
  };
  page.on("request", trackReviews);

  await page.getByRole("button", { name: "Checkout", exact: true }).click();
  await expect(
    page.getByRole("heading", {
      name: "Contact and delivery address",
      exact: true,
    }),
  ).toBeVisible();
  await page.getByLabel("Email", { exact: true }).fill(buyer.email);
  const shipping = page.getByRole("group", {
    name: "Shipping address",
    exact: true,
  });
  await shipping.getByLabel("First name", { exact: true }).fill(buyer.firstName);
  await shipping.getByLabel("Last name", { exact: true }).fill(buyer.lastName);
  await shipping.getByLabel("Address line 1", { exact: true }).fill(buyer.address1);
  await shipping.getByLabel("City", { exact: true }).fill(buyer.city);
  await shipping
    .getByLabel("Province or state", { exact: true })
    .fill(buyer.province);
  await shipping.getByLabel("Postal code", { exact: true }).fill(buyer.postalCode);
  const country = shipping.getByRole("combobox", { name: "Country", exact: true });
  await expect(country.locator("option:checked")).toHaveText(buyer.countryLabel);
  await shipping.getByLabel("Phone", { exact: true }).fill(buyer.phone);
  await page.waitForTimeout(1_200);

  await page
    .getByRole("button", { name: "Continue to delivery", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Delivery options", exact: true }),
  ).toBeVisible();
  await clickFirstSurfaceChoice(page, "Delivery options");
  await expect(
    page.getByRole("heading", { name: "Payment method", exact: true }),
  ).toBeVisible();
  await clickFirstSurfaceChoice(page, "Payment method");
  await expect(
    page.getByRole("heading", { name: "Review your order", exact: true }),
  ).toBeVisible();
  await page.waitForTimeout(1_200);

  const propose = page.getByRole("button", {
    name: "Review and place order",
    exact: true,
  });
  await propose.click();
  const firstReviewId = await currentReviewId(page);
  recorder.record("selection", {
    selection_kind: "placement_review",
    sequence: 1,
    review_id: firstReviewId,
  });
  await recorder.capture("first-review", [page.locator("address")]);
  expect(acceptRequests).toHaveLength(0);

  await page
    .getByRole("button", { name: "Cancel order placement", exact: true })
    .click();
  await expect.poll(() => rejectRequests.length).toBe(1);
  await expect(
    page.getByRole("heading", { name: "Confirm order placement", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "Order confirmed", exact: true }),
  ).toHaveCount(0);
  expect(acceptRequests).toHaveLength(0);
  await page.waitForTimeout(1_200);

  await propose.click();
  const secondReviewId = await currentReviewId(page);
  expect(secondReviewId).not.toBe(firstReviewId);
  recorder.record("selection", {
    selection_kind: "placement_review",
    sequence: 2,
    review_id: secondReviewId,
  });
  await recorder.capture("second-review", [page.locator("address")]);
  await page.getByRole("button", { name: "Place order", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Order confirmed", exact: true }),
  ).toBeVisible({ timeout: 60_000 });
  expect(rejectRequests).toHaveLength(1);
  expect(acceptRequests).toHaveLength(1);

  const confirmation = page.locator("section[data-confirmation]");
  await expect(confirmation).toHaveCount(1);
  const handle = await confirmation.getAttribute("data-confirmation");
  expect(handle).not.toBeNull();
  expect(handle).not.toBe("");
  const confirmationUrl = page.url();
  await recorder.capture("confirmation");
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(
    page.getByRole("heading", { name: "Order confirmed", exact: true }),
  ).toBeVisible();
  await expect(page.locator("section[data-confirmation]")).toHaveAttribute(
    "data-confirmation",
    handle!,
  );
  expect(page.url()).toBe(confirmationUrl);
  expect(acceptRequests).toHaveLength(1);
  await expectRouteDeckLive(page);
  await page.waitForTimeout(1_500);
  page.off("request", trackReviews);
}

async function clickFirstSurfaceChoice(
  page: Page,
  headingName: string,
): Promise<void> {
  const heading = page.getByRole("heading", { name: headingName, exact: true });
  const section = page.locator("section").filter({ has: heading });
  await expect(section).toHaveCount(1);
  const choices = section.getByRole("button");
  const count = await choices.count();
  for (let index = 0; index < count; index += 1) {
    const choice = choices.nth(index);
    if (!(await choice.isEnabled())) continue;
    await choice.click();
    await page.waitForTimeout(900);
    return;
  }
  throw new Error(`${headingName} has no enabled rendered choice.`);
}

async function currentReviewId(page: Page): Promise<string> {
  const heading = page.getByRole("heading", {
    name: "Confirm order placement",
    exact: true,
  });
  await expect(heading).toBeVisible();
  const id = await heading.getAttribute("id");
  if (id === null || !id.startsWith("review-") || id.length <= "review-".length) {
    throw new Error("The placement review heading has no review identity.");
  }
  return id.slice("review-".length);
}
