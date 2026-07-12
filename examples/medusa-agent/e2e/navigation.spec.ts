import {
  expectCart,
  expectProduct,
  openCart,
  selectVariantAndAddToCart,
} from "./support/buyer-flow";
import { expect, test } from "./support/fixtures";
import { PRODUCT } from "./support/test-data";

test("@scripted preserves exact deep-link, reload, back, forward, and cancel state", async ({
  page,
}) => {
  await page.goto(PRODUCT.path);
  await expect(page.getByTestId("medusa-buyer-app")).toBeVisible();
  await expectProduct(page);

  const history = page.getByRole("navigation", {
    name: "RouteDeck history",
    exact: true,
  });
  const back = history.getByRole("button", { name: "Back", exact: true });
  const forward = history.getByRole("button", {
    name: "Forward",
    exact: true,
  });
  const cancel = history.getByRole("button", {
    name: "Cancel",
    exact: true,
  });

  await expect(back).toBeEnabled();
  await back.click();
  await expect(
    page.getByRole("heading", { name: "Shop with Medusa", exact: true }),
  ).toBeVisible();
  await expect(forward).toBeEnabled();
  await forward.click();
  await expectProduct(page);

  await selectVariantAndAddToCart(page);
  await openCart(page);
  const cartUrl = page.url();

  await page.reload({ waitUntil: "domcontentloaded" });
  await expectCart(page);
  expect(page.url()).toBe(cartUrl);

  await expect(back).toBeEnabled();
  await back.click();
  await expectProduct(page);
  await expect(
    page.getByRole("radio", {
      name: PRODUCT.variantLabel,
      exact: true,
    }),
  ).toBeChecked();

  await expect(forward).toBeEnabled();
  await forward.click();
  await expectCart(page);

  await expect(cancel).toBeEnabled();
  await cancel.click();
  await expectProduct(page);
  await expect(forward).toBeEnabled();
  await forward.click();
  await expectCart(page);
});
