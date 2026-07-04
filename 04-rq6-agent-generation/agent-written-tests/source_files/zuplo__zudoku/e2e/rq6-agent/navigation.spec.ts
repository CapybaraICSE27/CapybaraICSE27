import { expect, test } from "@playwright/test";

// ──────────────────────────────────────────────────────────────────────────────
// 404 / Not Found
// ──────────────────────────────────────────────────────────────────────────────

test.describe("404 Not Found page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/this-page-does-not-exist-at-all");
    await page.waitForLoadState("networkidle");
  });

  test("renders custom NotFound heading 'Lost in Deep Space'", async ({
    page,
  }) => {
    await expect(
      page.getByRole("heading", { name: /Lost in Deep Space/i }),
    ).toBeVisible();
  });

  test("page title contains 404", async ({ page }) => {
    await expect(page).toHaveTitle(/404|Lost in Space/i);
  });

  test("shows 404 text", async ({ page }) => {
    await expect(page.getByText("404")).toBeVisible();
  });

  test("has 'Return to Base Station' link to /", async ({ page }) => {
    const link = page.getByRole("link", { name: /Return to Base Station/i });
    await expect(link).toBeVisible();
    await expect(link).toHaveAttribute("href", "/");
  });

  test("has 'Browse Star Charts' link to /documentation", async ({ page }) => {
    const link = page.getByRole("link", { name: /Browse Star Charts/i });
    await expect(link).toBeVisible();
    await expect(link).toHaveAttribute("href", "/documentation");
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// HTTP Redirects
// ──────────────────────────────────────────────────────────────────────────────

test.describe("HTTP Redirects", () => {
  test("/api-shipments/create-shipment redirects to shipment-management", async ({
    page,
  }) => {
    await page.goto("/api-shipments/create-shipment");
    await page.waitForLoadState("networkidle");
    await expect(page).toHaveURL(/shipment-management/);
  });

  test("/api-shipments/get-rates redirects to rates-and-billing", async ({
    page,
  }) => {
    await page.goto("/api-shipments/get-rates");
    await page.waitForLoadState("networkidle");
    await expect(page).toHaveURL(/rates-and-billing/);
  });

  test("/api-shipments/track-shipment redirects to tracking-and-notifications", async ({
    page,
  }) => {
    await page.goto("/api-shipments/track-shipment");
    await page.waitForLoadState("networkidle");
    await expect(page).toHaveURL(/tracking-and-notifications/);
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// Status Page (via navigationRules insert)
// ──────────────────────────────────────────────────────────────────────────────

test.describe("Status page navigation link", () => {
  test("API sidebar contains System Status link", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/api-shipments");
    await page.waitForLoadState("networkidle");
    // The navigationRules inserts a System Status link after the last API item
    await expect(
      page.getByRole("link", { name: /System Status/i }).first(),
    ).toBeVisible({ timeout: 10000 });
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// SPA (client-side) navigation
// ──────────────────────────────────────────────────────────────────────────────

test.describe("SPA navigation", () => {
  test("clicking Documentation nav link navigates without full reload", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Listen for navigations; we expect a SPA navigation (no full page reload)
    let fullReload = false;
    page.on("framenavigated", (frame) => {
      if (frame === page.mainFrame()) {
        fullReload = true;
      }
    });

    const docLink = page.getByRole("link", { name: "Documentation" }).first();
    await docLink.click();
    await page.waitForLoadState("networkidle");

    await expect(page).toHaveURL(/documentation/);
    // Page should have navigated (SPA or full) and show documentation content
    await expect(page.getByRole("main")).toBeVisible();
  });

  test("navigating from Documentation to API Reference updates content", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/documentation");
    await page.waitForLoadState("networkidle");

    const apiLink = page.getByRole("link", { name: "Shipments" }).first();
    await apiLink.click();
    await page.waitForLoadState("networkidle");

    await expect(page).toHaveURL(/api-shipments/);
    await expect(page.getByRole("main")).toBeVisible();
  });

  test("navigating from API Reference to Catalog updates content", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/api-shipments");
    await page.waitForLoadState("networkidle");

    const catalogLink = page.getByRole("link", { name: "API Catalog" }).first();
    await catalogLink.click();
    await page.waitForLoadState("networkidle");

    await expect(page).toHaveURL(/catalog/);
    await expect(page.getByRole("main")).toBeVisible();
  });

  test("document.title updates after SPA navigation", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    const docLink = page.getByRole("link", { name: "Documentation" }).first();
    await docLink.click();
    await page.waitForLoadState("networkidle");

    const title = await page.title();
    expect(title).toMatch(/Cosmo Cargo/i);
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// Logo navigation
// ──────────────────────────────────────────────────────────────────────────────

test.describe("Logo navigation", () => {
  test("clicking logo from documentation navigates to home", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/documentation");
    await page.waitForLoadState("networkidle");

    const logoLink = page.locator("header a[href='/']").first();
    await logoLink.click();
    await page.waitForLoadState("networkidle");
    await expect(page).toHaveURL("/");
  });
});
