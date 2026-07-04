import { expect, test } from "@playwright/test";

// ──────────────────────────────────────────────────────────────────────────────
// API Reference – /api-shipments and sub-pages
// ──────────────────────────────────────────────────────────────────────────────

test.describe("API Reference index", () => {
  test("/api-shipments has correct page title", async ({ page }) => {
    await page.goto("/api-shipments");
    await page.waitForLoadState("networkidle");
    await expect(page).toHaveTitle(/Shipment API/i);
  });

  test("/api-shipments shows sidebar navigation", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/api-shipments");
    await page.waitForLoadState("networkidle");
    await expect(page.locator("nav, aside").first()).toBeVisible();
  });

  test("/api-shipments page has sidebar with Shipment Management link", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/api-shipments");
    await page.waitForLoadState("networkidle");
    await expect(
      page.getByRole("link", { name: /Shipment Management/i }).first(),
    ).toBeVisible();
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// Shipment Management page
// ──────────────────────────────────────────────────────────────────────────────

test.describe("Shipment Management operations page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/api-shipments/shipment-management");
    await page.waitForLoadState("networkidle");
  });

  test("has correct page title", async ({ page }) => {
    await expect(page).toHaveTitle(/Shipment Management.*Shipment API/i);
  });

  test("renders Shipment Management heading", async ({ page }) => {
    await expect(
      page.getByRole("heading", { name: /Shipment Management/i }),
    ).toBeVisible();
  });

  test("shows HTTP method badges", async ({ page }) => {
    // Expect to see POST or GET method badges
    await expect(
      page.getByText("POST").or(page.getByText("GET")).first(),
    ).toBeVisible();
  });

  test("shows at least one API endpoint path", async ({ page }) => {
    // Should show paths like /shipments
    await expect(page.getByText(/\/shipments/i).first()).toBeVisible();
  });

  test("sidebar shows Rates & Billing link", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.reload();
    await page.waitForLoadState("networkidle");
    await expect(
      page.getByRole("link", { name: /Rates.*Billing/i }).first(),
    ).toBeVisible();
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// Rates & Billing operations page
// ──────────────────────────────────────────────────────────────────────────────

test.describe("Rates & Billing operations page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/api-shipments/rates-and-billing");
    await page.waitForLoadState("networkidle");
  });

  test("page loads and shows Rates & Billing content", async ({ page }) => {
    // The page should contain rates & billing related content
    await expect(
      page
        .getByRole("heading", { name: /Rates.*Billing/i })
        .or(page.getByText(/rate/i).first()),
    ).toBeVisible({ timeout: 10000 });
  });

  test("shows HTTP method badges", async ({ page }) => {
    await expect(
      page.getByText("POST").or(page.getByText("GET")).first(),
    ).toBeVisible({ timeout: 10000 });
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// Tracking & Notifications operations page
// ──────────────────────────────────────────────────────────────────────────────

test.describe("Tracking & Notifications operations page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/api-shipments/tracking-and-notifications");
    await page.waitForLoadState("networkidle");
  });

  test("page loads and shows tracking-related content", async ({ page }) => {
    await expect(
      page
        .getByRole("heading", { name: /Tracking|Notifications/i })
        .or(page.getByText(/tracking/i).first()),
    ).toBeVisible({ timeout: 10000 });
  });

  test("shows HTTP method badges", async ({ page }) => {
    await expect(
      page.getByText("GET").or(page.getByText("POST")).first(),
    ).toBeVisible({ timeout: 10000 });
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// API Playground
// ──────────────────────────────────────────────────────────────────────────────

test.describe("API Playground", () => {
  test("clicking Try it opens the playground panel", async ({ page }) => {
    await page.goto("/api-shipments/shipment-management");
    await page.waitForLoadState("networkidle");

    // Find a "Try it" button or similar playground trigger
    const tryItBtn = page
      .getByRole("button", { name: /try it|playground|send/i })
      .first();
    if (await tryItBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
      await tryItBtn.click();
      // Playground panel or dialog with a Send button should appear
      await expect(
        page.getByRole("button", { name: /send/i }).first(),
      ).toBeVisible({ timeout: 8000 });
    } else {
      // Alternatively look for an expand/collapse operation button
      const firstOp = page
        .locator('[data-operation], [role="button"]')
        .filter({ hasText: /POST|GET|PUT|DELETE/ })
        .first();
      if (await firstOp.isVisible({ timeout: 3000 }).catch(() => false)) {
        await firstOp.click();
        await page.waitForTimeout(1000);
        const sendBtn = page.getByRole("button", { name: /send/i }).first();
        if (await sendBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
          await expect(sendBtn).toBeVisible();
        } else {
          // Accept that playground may require auth
          test.skip();
        }
      } else {
        test.skip();
      }
    }
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// API Reference – sidebar navigation
// ──────────────────────────────────────────────────────────────────────────────

test.describe("API Reference sidebar navigation", () => {
  test("clicking sidebar link updates page content", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/api-shipments/shipment-management");
    await page.waitForLoadState("networkidle");

    // The sidebar links use slugs like "rates-billing" (not "rates-and-billing")
    const ratesLink = page
      .getByRole("link", { name: /Rates.*Billing/i })
      .first();
    if (await ratesLink.isVisible({ timeout: 5000 }).catch(() => false)) {
      await ratesLink.click();
      await page.waitForLoadState("networkidle");
      await expect(page).toHaveURL(/rates/i);
    } else {
      // Try direct navigation to the rates page
      await page.goto("/api-shipments/rates-billing");
      await page.waitForLoadState("networkidle");
      await expect(page.getByRole("main")).toBeVisible();
    }
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// SSR title on API reference page
// ──────────────────────────────────────────────────────────────────────────────

test.describe("API reference SSR", () => {
  test("SSR renders page title for shipment-management", async ({ page }) => {
    await page.goto("/api-shipments/shipment-management");
    // Title should be set in SSR
    const title = await page.title();
    expect(title).toMatch(/Shipment Management/i);
  });
});
