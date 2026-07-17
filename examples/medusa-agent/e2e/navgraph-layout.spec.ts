import { expect, test } from "./support/fixtures";

test("desktop Navgraph expands beside the buyer shell without covering it", async ({
  browserSafety,
  page,
}) => {
  await page.goto("/");
  await expect(page.getByTestId("medusa-buyer-app")).toBeVisible();

  const agentShell = page.locator("[data-agent-shell]");
  const navgraph = page.getByRole("complementary", {
    name: "Navgraph",
    exact: true,
  });
  const composer = page.getByLabel("Message the buyer assistant", {
    exact: true,
  });

  await page.getByRole("button", { name: "Open Navgraph", exact: true }).click();
  await expect(
    navgraph.getByRole("button", { name: "Close Navgraph", exact: true }),
  ).toHaveAttribute("aria-expanded", "true");

  const [agentShellBox, navgraphBox] = await Promise.all([
    agentShell.boundingBox(),
    navgraph.boundingBox(),
  ]);
  expect(agentShellBox).not.toBeNull();
  expect(navgraphBox).not.toBeNull();
  expect(
    agentShellBox!.x + agentShellBox!.width,
    "The expanded desktop Navgraph must begin after the buyer shell ends.",
  ).toBeLessThanOrEqual(navgraphBox!.x + 1);
  await expect(composer).toBeVisible();
  expect(await composer.isEditable()).toBe(true);
  browserSafety.assertClean();
});
