import {
  completeGuestCheckout,
  expectSessionRequiredConfirmationLink,
  openCart,
  openProductFromCatalog,
  selectVariantAndAddToCart,
} from "./support/buyer-flow";
import { expect, test } from "./support/fixtures";
import { releaseEvidenceFor } from "./support/release-evidence";
import { buyerForProject } from "./support/test-data";

test("@scripted completes one real Medusa guest order through RouteDeck UI", async ({
  browser,
  browserSafety,
  page,
}, testInfo) => {
  test.skip(
    process.env.ROUTEDECK_RELEASE_BUNDLE !== undefined &&
      testInfo.project.name !== "desktop-chromium",
    "The release proof measures exactly one complete-cart call on desktop Chromium.",
  );
  const buyer = buyerForProject(testInfo.project.name);
  const releaseEvidence = await releaseEvidenceFor(testInfo, page);
  await openProductFromCatalog(page, releaseEvidence);
  await selectVariantAndAddToCart(page);
  await openCart(page, releaseEvidence);

  const confirmationUrl = await completeGuestCheckout(
    page,
    buyer,
    releaseEvidence,
    { proveCheckoutPersistence: true },
  );
  const confirmationPath = new URL(confirmationUrl).pathname
    .split("/")
    .filter(Boolean);
  expect(confirmationPath[0]).toBe("orders");
  expect(confirmationPath[1]).toBeTruthy();
  expect(confirmationPath[2]).toBe("confirmation");

  const anonymousSafety = await expectSessionRequiredConfirmationLink(
    browser,
    confirmationUrl,
  );
  await releaseEvidence?.finalize(browserSafety, anonymousSafety);
});
