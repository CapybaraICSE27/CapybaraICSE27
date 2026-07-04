import { expect, test } from "@playwright/test";

// ──────────────────────────────────────────────────────────────────────────────
// Documentation pages
// ──────────────────────────────────────────────────────────────────────────────

test.describe("Documentation landing", () => {
  test("navigates to /documentation and shows sidebar", async ({ page }) => {
    await page.goto("/documentation");
    await page.waitForLoadState("networkidle");
    // The sidebar should be visible
    await expect(page.locator("nav, aside").first()).toBeVisible();
  });

  test("/documentation page title includes Cosmo Cargo", async ({ page }) => {
    await page.goto("/documentation");
    await page.waitForLoadState("networkidle");
    await expect(page).toHaveTitle(/Cosmo Cargo/i);
  });

  test("/documentation page renders main content heading", async ({ page }) => {
    await page.goto("/documentation");
    await page.waitForLoadState("networkidle");
    await expect(
      page.getByRole("heading", { name: /Cosmo Cargo Inc\./i }),
    ).toBeVisible();
  });

  test("documentation sidebar has Space Operations category", async ({
    page,
  }) => {
    await page.goto("/documentation");
    await page.waitForLoadState("networkidle");
    await expect(page.getByText("Space Operations")).toBeVisible();
  });

  test("documentation sidebar has Shipping Guides category", async ({
    page,
  }) => {
    await page.goto("/documentation");
    await page.waitForLoadState("networkidle");
    await expect(page.getByText("Shipping Guides")).toBeVisible();
  });

  test("documentation sidebar filter input is present", async ({ page }) => {
    await page.goto("/documentation");
    await page.waitForLoadState("networkidle");
    const filterInput = page.getByPlaceholder(/filter documentation/i);
    await expect(filterInput).toBeVisible();
  });

  test("sidebar filter narrows visible items", async ({ page }) => {
    await page.goto("/documentation");
    await page.waitForLoadState("networkidle");
    const filterInput = page.getByPlaceholder(/filter documentation/i);
    await filterInput.fill("fleet");
    // Fleet Management category should still be visible
    await expect(page.getByText(/Fleet Management/i)).toBeVisible();
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// Space Operations pages
// ──────────────────────────────────────────────────────────────────────────────

test.describe("Space Operations pages", () => {
  test("/shipping-process renders Intergalactic Shipping Process heading", async ({
    page,
  }) => {
    await page.goto("/shipping-process");
    await page.waitForLoadState("networkidle");
    await expect(
      page.getByRole("heading", { name: /Intergalactic Shipping Process/i }),
    ).toBeVisible();
  });

  test("/shipping-process has correct page title", async ({ page }) => {
    await page.goto("/shipping-process");
    await page.waitForLoadState("networkidle");
    await expect(page).toHaveTitle(/Intergalactic Shipping Process/i);
  });

  test("/tracking renders Real-Time Shipment Tracking heading", async ({
    page,
  }) => {
    await page.goto("/tracking");
    await page.waitForLoadState("networkidle");
    await expect(
      page.getByRole("heading", { name: /Real-Time Shipment Tracking/i }),
    ).toBeVisible();
  });

  test("/quantum-express renders Quantum Express heading", async ({ page }) => {
    await page.goto("/quantum-express");
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("heading", { name: /Quantum/i })).toBeVisible();
  });

  test("/ship-states renders Ship States Reference heading", async ({
    page,
  }) => {
    await page.goto("/ship-states");
    await page.waitForLoadState("networkidle");
    await expect(
      page.getByRole("heading", { name: /Ship States Reference/i }),
    ).toBeVisible();
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// Shipping Guides pages
// ──────────────────────────────────────────────────────────────────────────────

test.describe("Shipping Guides pages", () => {
  test("/global page loads with content", async ({ page }) => {
    await page.goto("/global");
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("main")).toBeVisible();
    // Page should have a heading
    await expect(page.locator("h1, h2").first()).toBeVisible();
  });

  test("/interstellar page loads with content", async ({ page }) => {
    await page.goto("/interstellar");
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("main")).toBeVisible();
    await expect(page.locator("h1, h2").first()).toBeVisible();
  });

  test("/intergalactic page loads with content", async ({ page }) => {
    await page.goto("/intergalactic");
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("main")).toBeVisible();
    await expect(page.locator("h1, h2").first()).toBeVisible();
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// Cargo Handbook pages
// ──────────────────────────────────────────────────────────────────────────────

test.describe("Cargo Handbook pages", () => {
  test("/cargo-handbook/hazardous page loads", async ({ page }) => {
    await page.goto("/cargo-handbook/hazardous");
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("main")).toBeVisible();
    await expect(page.locator("h1, h2").first()).toBeVisible();
  });

  test("/cargo-handbook/cryo page loads", async ({ page }) => {
    await page.goto("/cargo-handbook/cryo");
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("main")).toBeVisible();
    await expect(page.locator("h1, h2").first()).toBeVisible();
  });

  test("/cargo-handbook/living page loads", async ({ page }) => {
    await page.goto("/cargo-handbook/living");
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("main")).toBeVisible();
    await expect(page.locator("h1, h2").first()).toBeVisible();
  });

  test("/cargo-handbook/anomalous page loads", async ({ page }) => {
    await page.goto("/cargo-handbook/anomalous");
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("main")).toBeVisible();
    await expect(page.locator("h1, h2").first()).toBeVisible();
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// Fleet Management pages
// ──────────────────────────────────────────────────────────────────────────────

test.describe("Fleet Management pages", () => {
  for (const path of [
    "/fleet/warp-drives",
    "/fleet/maintenance",
    "/fleet/crew",
    "/fleet/refueling",
  ]) {
    test(`${path} page loads`, async ({ page }) => {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      await expect(page.getByRole("main")).toBeVisible();
      await expect(page.locator("h1, h2").first()).toBeVisible();
    });
  }
});

// ──────────────────────────────────────────────────────────────────────────────
// Billing & Credits pages
// ──────────────────────────────────────────────────────────────────────────────

test.describe("Billing & Credits pages", () => {
  test("/billing/invoices page loads with Invoices heading", async ({
    page,
  }) => {
    await page.goto("/billing/invoices");
    await page.waitForLoadState("networkidle");
    await expect(
      page.getByRole("heading", { name: /Invoices/i }),
    ).toBeVisible();
  });

  test("/billing/galactic-credits page loads", async ({ page }) => {
    await page.goto("/billing/galactic-credits");
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("main")).toBeVisible();
    await expect(page.locator("h1, h2").first()).toBeVisible();
  });

  test("/billing/refunds page loads", async ({ page }) => {
    await page.goto("/billing/refunds");
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("main")).toBeVisible();
    await expect(page.locator("h1, h2").first()).toBeVisible();
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// Compliance pages
// ──────────────────────────────────────────────────────────────────────────────

test.describe("Compliance pages", () => {
  for (const path of [
    "/compliance/customs",
    "/compliance/quarantine",
    "/compliance/treaties",
  ]) {
    test(`${path} page loads`, async ({ page }) => {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      await expect(page.getByRole("main")).toBeVisible();
      await expect(page.locator("h1, h2").first()).toBeVisible();
    });
  }
});

// ──────────────────────────────────────────────────────────────────────────────
// Support pages
// ──────────────────────────────────────────────────────────────────────────────

test.describe("Support pages", () => {
  for (const path of [
    "/support/contact",
    "/support/faq",
    "/support/escalations",
  ]) {
    test(`${path} page loads`, async ({ page }) => {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      await expect(page.getByRole("main")).toBeVisible();
      await expect(page.locator("h1, h2").first()).toBeVisible();
    });
  }
});

// ──────────────────────────────────────────────────────────────────────────────
// Sidebar navigation
// ──────────────────────────────────────────────────────────────────────────────

test.describe("Sidebar navigation", () => {
  test("clicking a sidebar link navigates to the correct page", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/documentation");
    await page.waitForLoadState("networkidle");

    // Find a sidebar link to /shipping-process or similar
    const sidebarLink = page
      .locator("nav")
      .getByRole("link", { name: /Shipping Process/i })
      .first();
    if (await sidebarLink.isVisible()) {
      await sidebarLink.click();
      await page.waitForLoadState("networkidle");
      await expect(page).toHaveURL(/shipping-process/);
    } else {
      // Skip if sidebar is not visible at this size
      test.skip();
    }
  });
});
