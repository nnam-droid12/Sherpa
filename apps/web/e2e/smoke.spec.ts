import { expect, test, type Page } from "@playwright/test";

function trackErrors(page: Page) {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  return errors;
}

test("landing page explains Sherpa and links to the dashboard", async ({ page }) => {
  const errors = trackErrors(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("PayPal checkout");
  await expect(page.locator("#how")).toBeVisible();
  await page.getByRole("link", { name: "Try it live, no sign-up" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  expect(errors).toEqual([]);
});

test("dashboard renders without an agent and offers the custom audit form", async ({ page }) => {
  const errors = trackErrors(page);
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: "Watch Sherpa fix a real checkout." })).toBeVisible();
  await expect(page.getByLabel("Store URL")).toBeVisible();
  await expect(page.getByRole("button", { name: "Start audit" })).toBeEnabled();
  expect(errors).toEqual([]);
});

test("run page shows the four stages and never crashes", async ({ page }) => {
  const errors = trackErrors(page);
  await page.goto("/runs/does-not-exist");
  const progress = page.getByRole("list", { name: "Progress" });
  for (const stage of ["Audit", "Fix", "Verify", "Agent-ready"]) {
    await expect(progress.getByText(stage, { exact: true })).toBeAttached();
  }
  await expect(page.locator("#audit")).toBeVisible();
  expect(errors).toEqual([]);
});

test("theme toggle switches and remembers the colour scheme", async ({ page }) => {
  await page.goto("/");
  const html = page.locator("html");
  const before = await html.getAttribute("data-theme");
  await page.getByRole("button", { name: "Toggle color theme" }).click();
  await expect(html).not.toHaveAttribute("data-theme", before ?? "");
  await page.reload();
  await expect(html).not.toHaveAttribute("data-theme", before ?? "");
});

test("primary navigation is reachable by keyboard", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Sherpa home" })).toBeFocused();
});

test("layout has no horizontal scroll", async ({ page }) => {
  for (const path of ["/", "/dashboard"]) {
    await page.goto(path);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow, path).toBeLessThanOrEqual(1);
  }
});
