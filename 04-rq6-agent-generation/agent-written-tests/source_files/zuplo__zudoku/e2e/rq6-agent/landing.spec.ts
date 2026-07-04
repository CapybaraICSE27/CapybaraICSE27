import { expect, test } from "@playwright/test";

// ──────────────────────────────────────────────────────────────────────────────
// Landing page – /, header, banner, footer, theme toggle
// ──────────────────────────────────────────────────────────────────────────────

test.describe("Landing page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
  });

  test("has correct page title", async ({ page }) => {
    await expect(page).toHaveTitle(/Home \| Cosmo Cargo Inc\./);
  });

  test("renders hero heading", async ({ page }) => {
    await expect(
      page.getByRole("heading", { name: /ship anywhere in the/i }),
    ).toBeVisible();
  });

  test("hero includes 'whole universe' highlight span", async ({ page }) => {
    await expect(page.getByText("whole universe")).toBeVisible();
  });

  test("hero CTA – Get started button links to /api-shipments", async ({
    page,
  }) => {
    const link = page.getByRole("link", { name: /get started/i });
    await expect(link).toBeVisible();
    await expect(link).toHaveAttribute("href", "/api-shipments");
  });

  test("hero CTA – Explore Zudoku external link", async ({ page }) => {
    const link = page.getByRole("link", { name: /explore zudoku/i });
    await expect(link).toBeVisible();
    await expect(link).toHaveAttribute(
      "href",
      expect.stringContaining("zudoku.dev"),
    );
  });

  test("cosmo.webp hero image rendered (large viewport)", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    const img = page.locator('img[src="/cosmo.webp"]');
    await expect(img).toBeAttached();
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// Banner
// ──────────────────────────────────────────────────────────────────────────────

test.describe("Announcement banner", () => {
  test("banner is visible with expected text", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await expect(page.getByText(/inter-galactic shipping/i)).toBeVisible();
  });

  test("banner can be dismissed", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    const bannerText = page.getByText(/inter-galactic shipping/i);
    await expect(bannerText).toBeVisible();
    // dismiss button is the circle-x button inside the banner
    const dismissBtn = page.locator("header").first().locator("button").first();
    await dismissBtn.click();
    await expect(bannerText).not.toBeVisible();
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// Header
// ──────────────────────────────────────────────────────────────────────────────

test.describe("Header", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    // Ensure desktop viewport
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/");
    await page.waitForLoadState("networkidle");
  });

  test("logo links to home", async ({ page }) => {
    const logoLink = page.locator("header a[href='/']").first();
    await expect(logoLink).toBeVisible();
    // logo img is inside the link
    await expect(logoLink.locator("img").first()).toBeVisible();
  });

  test("logo has correct alt text", async ({ page }) => {
    const logoImg = page.locator("header img[alt='Cosmo Cargo Inc.']").first();
    await expect(logoImg).toBeVisible();
  });

  test("Solutions dropdown opens and contains expected items", async ({
    page,
  }) => {
    await page.getByRole("button", { name: /solutions/i }).click();
    await expect(page.getByText("Shipment Tracking")).toBeVisible();
    await expect(page.getByText("Warp Logistics")).toBeVisible();
    await expect(page.getByText(/Browse all available/i)).toBeVisible();
  });

  test("Products dropdown opens and contains expected items", async ({
    page,
  }) => {
    await page.getByRole("button", { name: /products/i }).click();
    await expect(page.getByText(/Interstellar Express/i)).toBeVisible();
    await expect(page.getByText(/Quantum Freight/i)).toBeVisible();
    await expect(page.getByText(/Shipment API/i)).toBeVisible();
  });

  test("top nav contains Documentation link", async ({ page }) => {
    const link = page.getByRole("link", { name: "Documentation" }).first();
    await expect(link).toBeVisible();
    await expect(link).toHaveAttribute("href", "/documentation");
  });

  test("top nav contains Shipments link", async ({ page }) => {
    const link = page.getByRole("link", { name: "Shipments" }).first();
    await expect(link).toBeVisible();
    await expect(link).toHaveAttribute("href", "/api-shipments");
  });

  test("top nav contains API Catalog link", async ({ page }) => {
    const link = page.getByRole("link", { name: "API Catalog" }).first();
    await expect(link).toBeVisible();
    await expect(link).toHaveAttribute("href", "/catalog");
  });

  test("Login button is visible when unauthenticated", async ({ page }) => {
    await expect(page.getByRole("button", { name: /login/i })).toBeVisible();
  });

  test("theme toggle is visible", async ({ page }) => {
    // The toggle has aria-label="Toggle theme" before hydration
    const toggle = page.locator(
      'button[aria-label="Toggle theme"], button[aria-label="Switch to dark mode"], button[aria-label="Switch to light mode"]',
    );
    await expect(toggle).toBeVisible();
  });

  test("theme toggle switches to dark mode and back", async ({ page }) => {
    const toggle = page.locator(
      'button[aria-label="Toggle theme"], button[aria-label="Switch to dark mode"], button[aria-label="Switch to light mode"]',
    );
    await expect(toggle).toBeVisible();
    await toggle.click();
    // After clicking dark mode should be applied
    await expect(page.locator("html")).toHaveClass(/dark/);
    // Click again to go back
    const toggle2 = page.locator(
      'button[aria-label="Toggle theme"], button[aria-label="Switch to dark mode"], button[aria-label="Switch to light mode"]',
    );
    await toggle2.click();
    await expect(page.locator("html")).not.toHaveClass(/dark/);
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// Search
// ──────────────────────────────────────────────────────────────────────────────

test.describe("Search", () => {
  test("search button is visible", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    const searchBtn = page.getByRole("button", { name: /search/i });
    await expect(searchBtn).toBeVisible();
  });

  test("clicking search opens a dialog with a text input", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    const searchBtn = page.getByRole("button", { name: /search/i });
    await searchBtn.click();
    // A dialog with role="dialog" appears containing a Search input
    await expect(page.locator('[role="dialog"]').first()).toBeVisible({
      timeout: 5000,
    });
    // There should be a search text input
    await expect(
      page
        .locator('input[placeholder="Search..."], input[type="text"]')
        .first(),
    ).toBeVisible({ timeout: 5000 });
  });

  test("search dialog accepts input", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.getByRole("button", { name: /search/i }).click();
    const searchInput = page.locator('input[placeholder="Search..."]').first();
    await expect(searchInput).toBeVisible({ timeout: 5000 });
    await searchInput.fill("shipment");
    await expect(searchInput).toHaveValue("shipment");
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// Footer
// ──────────────────────────────────────────────────────────────────────────────

test.describe("Footer", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
  });

  test("footer is present with copyright text", async ({ page }) => {
    await expect(page.locator("footer")).toBeVisible();
    await expect(
      page.getByText(/Zuplo, Inc. All rights reserved/i),
    ).toBeVisible();
  });

  test("footer has Product column with Features and Docs links", async ({
    page,
  }) => {
    const footer = page.locator("footer");
    await expect(footer.getByText("Product")).toBeVisible();
    await expect(footer.getByText("Features")).toBeVisible();
    await expect(footer.getByText("Docs")).toBeVisible();
  });

  test("footer has Company column with About, Blog, Careers links", async ({
    page,
  }) => {
    const footer = page.locator("footer");
    await expect(footer.getByText("Company")).toBeVisible();
    await expect(footer.getByRole("link", { name: "About" })).toBeVisible();
    await expect(footer.getByRole("link", { name: "Blog" })).toBeVisible();
    await expect(footer.getByRole("link", { name: "Careers" })).toBeVisible();
  });

  test("footer has Resources column", async ({ page }) => {
    const footer = page.locator("footer");
    await expect(footer.getByText("Resources")).toBeVisible();
  });

  test("footer has Legal column with Privacy, Terms, Security links", async ({
    page,
  }) => {
    const footer = page.locator("footer");
    await expect(footer.getByText("Legal")).toBeVisible();
    await expect(footer.getByRole("link", { name: "Privacy" })).toBeVisible();
    await expect(footer.getByRole("link", { name: "Terms" })).toBeVisible();
    await expect(footer.getByRole("link", { name: "Security" })).toBeVisible();
  });

  test("footer has social icons (GitHub, X, Discord)", async ({ page }) => {
    const footer = page.locator("footer");
    await expect(footer.locator('img[alt="github"]')).toBeVisible();
    await expect(footer.locator('img[alt="x"]')).toBeVisible();
    await expect(footer.locator('img[alt="discord"]')).toBeVisible();
  });

  test("footer contains Zudoku logo", async ({ page }) => {
    const footer = page.locator("footer");
    await expect(
      footer.locator('img[alt="Zudoku by Zuplo"]').first(),
    ).toBeVisible();
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// SSR / Meta
// ──────────────────────────────────────────────────────────────────────────────

test.describe("SSR and meta tags", () => {
  test("page title set via SSR on landing page", async ({ page }) => {
    const response = await page.goto("/");
    // Check the <title> tag in the initial HTML
    const title = await page.title();
    expect(title).toMatch(/Cosmo Cargo/);
  });

  test("meta description set on landing page", async ({ page }) => {
    await page.goto("/");
    const metaDesc = await page
      .locator('meta[name="description"]')
      .getAttribute("content");
    expect(metaDesc).toMatch(/shipping/i);
  });

  test("plugin-injected meta tag is present", async ({ page }) => {
    await page.goto("/");
    const metaTag = page.locator('meta[name="cosmo-cargo-head-test"]');
    await expect(metaTag).toHaveAttribute("content", "verified");
  });

  test("plugin head script sets window flag", async ({ page }) => {
    await page.goto("/");
    const flag = await page.evaluate(() => (window as any).__COSMO_HEAD_TEST);
    expect(flag).toBe(true);
  });
});
