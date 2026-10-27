import { test, expect } from "@playwright/test";
test("foundation navigation and persistent appearance", async ({ page }) => {
  await page.goto("/today");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Make room for what matters.",
  );
  await page.getByRole("link", { name: "Goals", exact: true }).click();
  await expect(page.getByText("Coming in a later milestone")).toBeVisible();
  await page.getByRole("link", { name: "Settings", exact: true }).click();
  await page.getByLabel("Color theme").selectOption("dark");
  await page.reload();
  await expect(page.getByLabel("Color theme")).toHaveValue("dark");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
});
test("mobile navigation and layout", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/today");
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page.getByRole("link", { name: "Weekly plan", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Make a little room for your goals.",
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});
