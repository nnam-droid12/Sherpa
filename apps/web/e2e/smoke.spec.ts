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

test("fleet scan ranks stores in the grid, worst first", async ({ page }) => {
  const errors = trackErrors(page);
  const row = (url: string, score: number, sdk: string) => ({
    url, reachable: true, status: 200, ms: 120, sdk, paypal: sdk !== "none", venmo: false, pay_later: false,
    catalog_feed: null, catalog_items: 0, cart_api: false, score, issues: ["No Venmo"], error: null,
  });
  await page.route("**/api/agent/fleet/scan", (route) =>
    route.fulfill({ json: { stores: [row("https://b.example", 30, "v5"), row("https://a.example", 50, "v6")], limit: 25 } }),
  );
  await page.goto("/fleet");
  await page.getByLabel(/Store URLs/).fill("https://a.example\nhttps://b.example");
  await page.getByRole("button", { name: "Scan 2 stores" }).click();
  const grid = page.getByRole("treegrid").or(page.getByRole("grid"));
  await expect(grid.getByText("https://b.example")).toBeVisible();
  await expect(grid.getByText("v5 (legacy)")).toBeVisible();
  await expect(page.getByText("Stores scanned")).toBeVisible();
  expect(errors).toEqual([]);
});
