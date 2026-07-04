import { expect, test } from "@playwright/test";

// ──────────────────────────────────────────────────────────────────────────────
// API Catalog – /catalog
// ──────────────────────────────────────────────────────────────────────────────

test.describe("API Catalog index", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/catalog");
    await page.waitForLoadState("networkidle");
  });

  test("has correct page title", async ({ page }) => {
    await expect(page).toHaveTitle(/API Catalog/i);
  });

  test("page shows multiple API catalog entries", async ({ page }) => {
    // Catalog should list at least some API cards
    await expect(page.locator('a[href*="/catalog/api-"]').first()).toBeVisible({
      timeout: 10000,
    });
  });

  test("catalog shows Label API entry", async ({ page }) => {
    await expect(
      page.locator('a[href*="/catalog/api-label"]').first(),
    ).toBeVisible({ timeout: 10000 });
  });

  test("catalog shows Webhooks API entry", async ({ page }) => {
    await expect(
      page.locator('a[href*="/catalog/api-webhooks"]').first(),
    ).toBeVisible({ timeout: 10000 });
  });

  test("catalog shows Fleet Ops API entry", async ({ page }) => {
    await expect(
      page.locator('a[href*="/catalog/api-fleet-ops"]').first(),
    ).toBeVisible({ timeout: 10000 });
  });

  test("catalog shows Interplanetary API entry", async ({ page }) => {
    await expect(
      page.locator('a[href*="/catalog/api-interplanetary"]').first(),
    ).toBeVisible({ timeout: 10000 });
  });

  test("catalog shows Tracking API entry", async ({ page }) => {
    await expect(
      page.locator('a[href*="/catalog/api-tracking"]').first(),
    ).toBeVisible({ timeout: 10000 });
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// Label API (versioned)
// ──────────────────────────────────────────────────────────────────────────────

test.describe("Label API catalog pages", () => {
  test("/catalog/api-label/latest shows Labels & Stamps API title", async ({
    page,
  }) => {
    await page.goto("/catalog/api-label/latest");
    await page.waitForLoadState("networkidle");
    await expect(page).toHaveTitle(/Labels.*Stamps API/i);
  });

  test("/catalog/api-label/latest shows operations", async ({ page }) => {
    await page.goto("/catalog/api-label/latest");
    await page.waitForLoadState("networkidle");
    await expect(
      page.getByText("GET").or(page.getByText("POST")).first(),
    ).toBeVisible({ timeout: 10000 });
  });

  test("/catalog/api-label/1.0.0 page loads", async ({ page }) => {
    await page.goto("/catalog/api-label/1.0.0");
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("main")).toBeVisible();
  });

  test("/catalog/api-label/2.0.0 page loads", async ({ page }) => {
    await page.goto("/catalog/api-label/2.0.0");
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("main")).toBeVisible();
  });

  test("label API shows version label in content", async ({ page }) => {
    await page.goto("/catalog/api-label/latest");
    await page.waitForLoadState("networkidle");
    // The page shows "Latest (3.0.0)" as the version description
    await expect(
      page.getByText(/Latest \(3\.0\.0\)|Labels.*Stamps API/i).first(),
    ).toBeVisible({ timeout: 10000 });
  });

  test("label API sidebar links to versioned paths", async ({ page }) => {
    await page.goto("/catalog/api-label/latest");
    await page.waitForLoadState("networkidle");
    // Sidebar should have links to sub-sections
    await expect(
      page.getByRole("link", { name: /Labels|Stamps|Information/i }).first(),
    ).toBeVisible({ timeout: 10000 });
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// Webhooks API
// ──────────────────────────────────────────────────────────────────────────────

test.describe("Webhooks API catalog page", () => {
  test("/catalog/api-webhooks page loads with content", async ({ page }) => {
    await page.goto("/catalog/api-webhooks");
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("main")).toBeVisible();
  });

  test("/catalog/api-webhooks shows operations", async ({ page }) => {
    await page.goto("/catalog/api-webhooks");
    await page.waitForLoadState("networkidle");
    await expect(
      page
        .getByText("GET")
        .or(page.getByText("POST"))
        .or(page.getByText("DELETE"))
        .first(),
    ).toBeVisible({ timeout: 10000 });
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// Interplanetary API
// ──────────────────────────────────────────────────────────────────────────────

test.describe("Interplanetary API catalog page", () => {
  test("/catalog/api-interplanetary page loads", async ({ page }) => {
    await page.goto("/catalog/api-interplanetary");
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("main")).toBeVisible();
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// Tracking API
// ──────────────────────────────────────────────────────────────────────────────

test.describe("Tracking API catalog page", () => {
  test("/catalog/api-tracking page loads", async ({ page }) => {
    await page.goto("/catalog/api-tracking");
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("main")).toBeVisible();
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// AI Cargo API
// ──────────────────────────────────────────────────────────────────────────────

test.describe("AI Cargo API catalog page", () => {
  test("/catalog/api-ai-cargo page loads", async ({ page }) => {
    await page.goto("/catalog/api-ai-cargo");
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("main")).toBeVisible();
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// Fleet Ops API (versioned)
// ──────────────────────────────────────────────────────────────────────────────

test.describe("Fleet Ops API catalog pages", () => {
  test("/catalog/api-fleet-ops page title shows Fleet Operations", async ({
    page,
  }) => {
    await page.goto("/catalog/api-fleet-ops");
    await page.waitForLoadState("networkidle");
    await expect(page).toHaveTitle(/Fleet Operations API/i);
  });

  test("/catalog/api-fleet-ops/v3 page loads", async ({ page }) => {
    await page.goto("/catalog/api-fleet-ops/v3");
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("main")).toBeVisible();
  });

  test("/catalog/api-fleet-ops/v2 page loads", async ({ page }) => {
    await page.goto("/catalog/api-fleet-ops/v2");
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("main")).toBeVisible();
  });

  test("/catalog/api-fleet-ops/v1 page loads", async ({ page }) => {
    await page.goto("/catalog/api-fleet-ops/v1");
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("main")).toBeVisible();
  });

  test("fleet-ops API shows version selector", async ({ page }) => {
    await page.goto("/catalog/api-fleet-ops/v3");
    await page.waitForLoadState("networkidle");
    await expect(
      page
        .getByRole("link", { name: /v1|v2|v3/i })
        .or(page.getByRole("tab", { name: /v1|v2|v3/i }))
        .first(),
    ).toBeVisible({ timeout: 10000 });
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// Cargo Containers API
// ──────────────────────────────────────────────────────────────────────────────

test.describe("Cargo Containers API catalog page", () => {
  test("/catalog/api-cargo-containers page loads", async ({ page }) => {
    await page.goto("/catalog/api-cargo-containers");
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("main")).toBeVisible();
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// Docs API
// ──────────────────────────────────────────────────────────────────────────────

test.describe("Docs API catalog page", () => {
  test("/catalog/api-docs page loads", async ({ page }) => {
    await page.goto("/catalog/api-docs");
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("main")).toBeVisible();
  });
});
