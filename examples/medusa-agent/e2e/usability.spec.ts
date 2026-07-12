import type { Locator, Page } from "@playwright/test";

import {
  expectCart,
  expectProduct,
  openCart,
  selectVariantAndAddToCart,
} from "./support/buyer-flow";
import { expect, test } from "./support/fixtures";
import { PRODUCT, buyerForProject } from "./support/test-data";

const DISPATCH_PATH = "/api/routedeck/dispatch";

test("@usability browses, searches, mutates a real cart, and restores checkout", async ({
  page,
}, testInfo) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Shop with Medusa", exact: true }),
  ).toBeVisible();

  await clickWithDispatch(
    page,
    page.getByRole("button", { name: "Browse products", exact: true }),
  );
  await expect(
    page.getByRole("heading", { name: "Products", exact: true }),
  ).toBeVisible();

  await page
    .getByLabel("Search the catalog", { exact: true })
    .fill("T-Shirt");
  await clickWithDispatch(
    page,
    page.getByRole("button", { name: "Search", exact: true }),
  );
  await expect(
    page.getByRole("heading", {
      name: "Results for “T-Shirt”",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: PRODUCT.catalogLinkLabel, exact: true }),
  ).toHaveCount(1);

  await clickWithDispatch(
    page,
    page.getByRole("button", { name: "Clear search", exact: true }),
  );
  await expect(
    page.getByRole("heading", { name: "Products", exact: true }),
  ).toBeVisible();

  await page
    .getByRole("link", { name: PRODUCT.catalogLinkLabel, exact: true })
    .click();
  await expectProduct(page);
  await selectVariantAndAddToCart(page);
  await openCart(page);
  await expectCart(page);

  const cartUrl = page.url();
  await page.reload({ waitUntil: "domcontentloaded" });
  await expectCart(page);
  expect(page.url()).toBe(cartUrl);

  await clickWithDispatch(
    page,
    page.getByRole("button", { name: "Checkout", exact: true }),
  );
  await expect(
    page.getByRole("heading", {
      name: "Contact and delivery address",
      exact: true,
    }),
  ).toBeVisible();

  const checkoutUrl = page.url();
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(
    page.getByRole("heading", {
      name: "Contact and delivery address",
      exact: true,
    }),
  ).toBeVisible();
  expect(page.url()).toBe(checkoutUrl);

  const buyer = buyerForProject(testInfo.project.name);
  await page.getByLabel("Email", { exact: true }).fill(buyer.email);
  const shippingAddress = page.getByRole("group", {
    name: "Shipping address",
    exact: true,
  });
  await shippingAddress
    .getByLabel("First name", { exact: true })
    .fill(buyer.firstName);
  await shippingAddress
    .getByLabel("Last name", { exact: true })
    .fill(buyer.lastName);
  await shippingAddress
    .getByLabel("Address line 1", { exact: true })
    .fill(buyer.address1);
  await shippingAddress.getByLabel("City", { exact: true }).fill(buyer.city);
  await shippingAddress
    .getByLabel("Province or state", { exact: true })
    .fill(buyer.province);
  await shippingAddress
    .getByLabel("Postal code", { exact: true })
    .fill(buyer.postalCode);
  await shippingAddress.getByLabel("Phone", { exact: true }).fill(buyer.phone);

  await clickWithDispatch(
    page,
    page.getByRole("button", { name: "Continue to delivery", exact: true }),
  );
  await expect(
    page.getByRole("heading", { name: "Delivery options", exact: true }),
  ).toBeVisible();

  await clickWithDispatch(
    page,
    page.getByRole("button", { name: PRODUCT.shippingLabel, exact: true }),
  );
  await expect(
    page.getByRole("heading", { name: "Payment method", exact: true }),
  ).toBeVisible();

  await clickWithDispatch(
    page,
    page.getByRole("button", { name: PRODUCT.paymentLabel, exact: true }),
  );
  await expect(
    page.getByRole("heading", { name: "Review your order", exact: true }),
  ).toBeVisible();

  await clickWithDispatch(
    page,
    page.getByRole("button", {
      name: "Review and place order",
      exact: true,
    }),
  );
  await expect(
    page.getByRole("heading", { name: "Confirm order placement", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Place order", exact: true }),
  ).toBeVisible();

  const reviewUrl = page.url();
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(
    page.getByRole("heading", { name: "Confirm order placement", exact: true }),
  ).toBeVisible();
  expect(page.url()).toBe(reviewUrl);

  await expect(
    page
      .getByRole("complementary", {
        name: "RouteDeck session status",
        exact: true,
      })
      .getByText("live", { exact: true }),
  ).toBeVisible();
});

async function clickWithDispatch(page: Page, locator: Locator): Promise<void> {
  const response = page.waitForResponse((candidate) => {
    const request = candidate.request();
    return (
      request.method() === "POST" &&
      new URL(candidate.url()).pathname === DISPATCH_PATH
    );
  });
  await locator.click();
  expect((await response).ok()).toBe(true);
  await expect(page.locator("[data-routedeck-surface][inert]")).toHaveCount(0);
}
