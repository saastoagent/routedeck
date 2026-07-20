import {
  expect,
  type Browser,
  type Page,
  type Request,
} from "@playwright/test";

import { installBrowserSafety, type BrowserSafety } from "./fixtures";
import type {
  BrowserEvidenceStage,
  BrowserFlowEvidence,
} from "./release-evidence";
import { PRODUCT, type BuyerProfile } from "./test-data";

const ROUTEDECK_DISPATCH_PATH = "/api/routedeck/dispatch";
const ROUTEDECK_SESSIONS_PATH = "/api/routedeck/sessions";
const REAL_CHECKOUT_STAGE_TIMEOUT_MS = 60_000;

export type CheckoutFlowStage =
  | "contact"
  | "delivery"
  | "payment"
  | "review"
  | "approval"
  | "confirmation";

export interface CheckoutFlowOptions {
  proveCheckoutPersistence?: boolean;
  onStage?(stage: CheckoutFlowStage, page: Page): Promise<void>;
}

export async function openProductFromCatalog(
  page: Page,
  evidence?: BrowserFlowEvidence,
): Promise<void> {
  await page.goto("/");
  await expect(page.getByTestId("medusa-buyer-app")).toBeVisible();
  await page
    .getByRole("button", { name: "Browse products", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Products", exact: true }),
  ).toBeVisible();
  await expectRouteDeckLive(page);
  await captureEvidence(evidence, page, "browse");
  await page
    .getByRole("link", { name: PRODUCT.catalogLinkLabel, exact: true })
    .click();
  await expectProduct(page);
}

export async function expectProduct(page: Page): Promise<void> {
  await expect(
    page.getByRole("heading", { name: PRODUCT.title, exact: true }),
  ).toBeVisible();
  await expect(page).toHaveURL(new URL(PRODUCT.path, page.url()).toString());
  await expectRouteDeckLive(page);
}

export async function selectVariantAndAddToCart(
  page: Page,
  quantityValues: readonly string[] = ["1"],
): Promise<void> {
  const variant = page.getByRole("radio", {
    name: PRODUCT.variantLabel,
    exact: true,
  });
  const selectionResponse = waitForSuccessfulPost(
    page,
    ROUTEDECK_DISPATCH_PATH,
  );
  await variant.click();
  await selectionResponse;
  await expect(variant).toBeChecked();
  await expectRouteDeckLive(page);

  const quantity = page.getByRole("spinbutton", {
    name: "Quantity",
    exact: true,
  });
  await expect(quantity).toBeEnabled();
  for (const [index, value] of quantityValues.entries()) {
    await quantity.fill(value);
    if (index < quantityValues.length - 1) {
      await page.waitForTimeout(350);
    }
  }

  const addForm = page.locator("form[data-catalog-add-to-cart]");
  const addButton = page.getByRole("button", {
    name: "Add to cart",
    exact: true,
  });
  const dispatchResponse = waitForSuccessfulPost(
    page,
    ROUTEDECK_DISPATCH_PATH,
  );
  await addButton.click();
  await expect(addForm).toHaveAttribute("aria-busy", "true");
  await dispatchResponse;
  await expect(addForm).toHaveAttribute("aria-busy", "false");
  await expect(addButton).toBeEnabled();
  await expectRouteDeckLive(page);
}

export async function openCart(
  page: Page,
  evidence?: BrowserFlowEvidence,
): Promise<void> {
  const dispatchResponse = waitForSuccessfulPost(
    page,
    ROUTEDECK_DISPATCH_PATH,
  );
  await page.getByRole("button", { name: "View cart", exact: true }).click();
  await dispatchResponse;
  await expectCart(page);
  await captureEvidence(evidence, page, "cart");
}

export async function expectCart(page: Page): Promise<void> {
  await expect(
    page.getByRole("heading", { name: "Your cart", exact: true }),
  ).toBeVisible();
  await expect(page.locator("[data-cart-line]")).toHaveCount(1);
  await expectRouteDeckLive(page);
}

export async function completeGuestCheckout(
  page: Page,
  buyer: BuyerProfile,
  evidence?: BrowserFlowEvidence,
  options?: CheckoutFlowOptions,
): Promise<string> {
  const proveCheckoutPersistence = options?.proveCheckoutPersistence ?? true;
  evidence?.registerSensitiveValues([
    buyer.email,
    buyer.firstName,
    buyer.lastName,
    buyer.address1,
    buyer.city,
    buyer.province,
    buyer.postalCode,
    buyer.phone,
  ]);
  const approvalRequests: Request[] = [];
  const trackApproval = (request: Request) => {
    if (isReviewAcceptance(request)) approvalRequests.push(request);
  };
  page.on("request", trackApproval);

  await page
    .getByRole("button", { name: "Checkout", exact: true })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "Contact and delivery address",
      exact: true,
    }),
  ).toBeVisible();
  await expectRouteDeckLive(page);
  await observeStage(options, "contact", page);

  await page.getByLabel("Email", { exact: true }).fill(buyer.email);
  const shipping = page.getByRole("group", {
    name: "Shipping address",
    exact: true,
  });
  await shipping
    .getByLabel("First name", { exact: true })
    .fill(buyer.firstName);
  await shipping
    .getByLabel("Last name", { exact: true })
    .fill(buyer.lastName);
  await shipping
    .getByLabel("Address line 1", { exact: true })
    .fill(buyer.address1);
  await shipping.getByLabel("City", { exact: true }).fill(buyer.city);
  await shipping
    .getByLabel("Province or state", { exact: true })
    .fill(buyer.province);
  await shipping
    .getByLabel("Postal code", { exact: true })
    .fill(buyer.postalCode);
  const country = shipping.getByRole("combobox", {
    name: "Country",
    exact: true,
  });
  await expect(country.locator("option:checked")).toHaveText(
    buyer.countryLabel,
  );
  await shipping.getByLabel("Phone", { exact: true }).fill(buyer.phone);

  await page
    .getByRole("button", { name: "Continue to delivery", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Delivery options", exact: true }),
  ).toBeVisible({ timeout: REAL_CHECKOUT_STAGE_TIMEOUT_MS });
  await expectRouteDeckLive(page);
  await observeStage(options, "delivery", page);

  await page
    .getByRole("button", { name: PRODUCT.shippingLabel, exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Payment method", exact: true }),
  ).toBeVisible({ timeout: REAL_CHECKOUT_STAGE_TIMEOUT_MS });
  await expectRouteDeckLive(page);
  await observeStage(options, "payment", page);

  await page
    .getByRole("button", { name: PRODUCT.paymentLabel, exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Review your order", exact: true }),
  ).toBeVisible({ timeout: REAL_CHECKOUT_STAGE_TIMEOUT_MS });
  await expectRouteDeckLive(page);
  await expect(
    page.getByRole("heading", { name: "Delivery address", exact: true }),
  ).toBeVisible();
  await observeStage(options, "review", page);

  await page
    .getByRole("button", { name: "Review and place order", exact: true })
    .click();
  await expectPendingApproval(page);

  if (proveCheckoutPersistence) {
    await page.reload({ waitUntil: "domcontentloaded" });
    await expectPendingApproval(page);
    await expect(
      page.getByRole("heading", { name: "Delivery address", exact: true }),
    ).toBeVisible();
  }
  await captureEvidence(evidence, page, "review-pending");
  expect(approvalRequests).toHaveLength(0);
  await observeStage(options, "approval", page);

  await page
    .getByRole("button", { name: "Place order", exact: true })
    .click();
  await expect(
    page.locator("#order-confirmation-title"),
  ).toBeVisible({ timeout: 60_000 });
  await expectRouteDeckLive(page);
  await observeStage(options, "confirmation", page);
  page.off("request", trackApproval);

  expect(approvalRequests).toHaveLength(1);
  const confirmation = page.locator("section[data-confirmation]");
  await expect(confirmation).toHaveCount(1);
  const confirmationHandle = await confirmation.getAttribute("data-confirmation");
  expect(confirmationHandle).not.toBeNull();
  expect(confirmationHandle).not.toBe("");

  const confirmationUrl = page.url();
  if (proveCheckoutPersistence) {
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(
      page.locator("#order-confirmation-title"),
    ).toBeVisible();
    await expectRouteDeckLive(page);
    await expect(page.locator("section[data-confirmation]")).toHaveAttribute(
      "data-confirmation",
      confirmationHandle!,
    );
    expect(page.url()).toBe(confirmationUrl);
  }
  await captureEvidence(evidence, page, "confirmation");
  return confirmationUrl;
}

export async function expectSessionRequiredConfirmationLink(
  browser: Browser,
  confirmationUrl: string,
): Promise<BrowserSafety> {
  const context = await browser.newContext({ serviceWorkers: "block" });
  const safety = await installBrowserSafety(context, "anonymous");
  const sessionCreationRequests: Request[] = [];
  context.on("request", (request) => {
    const url = new URL(request.url());
    if (
      request.method() === "POST" &&
      url.pathname === ROUTEDECK_SESSIONS_PATH
    ) {
      sessionCreationRequests.push(request);
    }
  });

  try {
    expect(await context.cookies()).toHaveLength(0);
    const page = await context.newPage();
    await page.goto(confirmationUrl);
    const alert = page.getByRole("alert");
    await expect(
      alert.getByRole("heading", {
        name: "Buyer session unavailable",
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      alert.getByRole("button", {
        name: "Start a new buyer session",
        exact: true,
      }),
    ).toBeVisible();
    expect(sessionCreationRequests).toHaveLength(0);
  } finally {
    await context.close();
    safety.assertClean();
  }
  return safety;
}

async function expectPendingApproval(page: Page): Promise<void> {
  await expect(
    page.getByRole("heading", {
      name: "Confirm order placement",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Place order", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", {
      name: "Cancel order placement",
      exact: true,
    }),
  ).toBeVisible();
  await expectRouteDeckLive(page);
}

async function expectRouteDeckLive(page: Page): Promise<void> {
  const navgraph = page.getByRole("complementary", {
    name: "Navgraph",
    exact: true,
  });
  await expect(navgraph).toHaveAttribute("data-status", "live");
}

async function captureEvidence(
  evidence: BrowserFlowEvidence | undefined,
  page: Page,
  stage: BrowserEvidenceStage,
): Promise<void> {
  await evidence?.capture(page, stage);
}

async function observeStage(
  options: CheckoutFlowOptions | undefined,
  stage: CheckoutFlowStage,
  page: Page,
): Promise<void> {
  await options?.onStage?.(stage, page);
}

function isReviewAcceptance(request: Request): boolean {
  if (request.method() !== "POST") return false;
  const segments = new URL(request.url()).pathname.split("/").filter(Boolean);
  return (
    segments.length === 5 &&
    segments[0] === "api" &&
    segments[1] === "routedeck" &&
    segments[2] === "reviews" &&
    segments[3]!.length > 0 &&
    segments[4] === "accept"
  );
}

async function waitForSuccessfulPost(
  page: Page,
  pathname: string,
): Promise<void> {
  const response = await page.waitForResponse((candidate) => {
    const request = candidate.request();
    return (
      request.method() === "POST" &&
      new URL(candidate.url()).pathname === pathname
    );
  });
  expect(response.ok(), `${pathname} must succeed`).toBe(true);
}
