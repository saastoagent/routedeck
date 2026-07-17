import { expect, test } from "@playwright/test";

test("shareable storefront automatically replaces a contract-mismatched buyer session", async ({
  page,
}) => {
  let injectedContractMismatch = false;
  await page.route("**/api/routedeck/session", async (route) => {
    const request = route.request();
    if (request.method() !== "GET" || injectedContractMismatch) {
      await route.continue();
      return;
    }

    injectedContractMismatch = true;
    await route.fulfill({
      status: 409,
      contentType: "application/json",
      body: JSON.stringify({
        failure: {
          code: "session_upgrade_required",
          correlation_id: "e2e-shareable-contract-mismatch",
          kind: "state_conflict",
          phase: "session_validation",
          operation_id: null,
          request_id: null,
          public_message: "This session requires an application upgrade.",
          recovery_directive: null,
          safe_details: {
            affected_capability: null,
            provider: null,
            provider_code: null,
            http_status: null,
            delivery_phase: null,
          },
        },
      }),
    });
  });

  const sessionCreated = page.waitForResponse((response) => {
    const request = response.request();
    return (
      request.method() === "POST" &&
      new URL(response.url()).pathname === "/api/routedeck/sessions"
    );
  });

  await page.goto("/");

  expect((await sessionCreated).status()).toBe(201);
  await expect(page.getByTestId("medusa-buyer-app")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Buyer session contract changed" }),
  ).toHaveCount(0);
  await expect(page.getByText("Restoring your buyer session")).toHaveCount(0);
  expect(
    (await page.context().cookies()).some(
      (cookie) => cookie.name === "routedeck_guest" && cookie.value.length > 0,
    ),
  ).toBe(true);
});
