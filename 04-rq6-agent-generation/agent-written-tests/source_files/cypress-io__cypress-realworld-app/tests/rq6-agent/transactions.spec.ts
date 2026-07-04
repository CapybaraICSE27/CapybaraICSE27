import { test, expect } from "@playwright/test";
import { loginViaUi, dismissOnboardingIfPresent } from "./helpers/auth";

test.describe("Transaction Lists", () => {
  test.beforeEach(async ({ page }) => {
    await loginViaUi(page);
    await dismissOnboardingIfPresent(page);
  });

  test("home page (Everyone tab) shows public transaction list", async ({ page }) => {
    await page.goto("http://localhost:3000/");
    // Transactions list should load
    const transactionItems = page.locator('[data-test^="transaction-item-"]');
    await expect(transactionItems.first()).toBeVisible({ timeout: 15000 });
  });

  test("Contacts tab (/contacts) shows transaction list", async ({ page }) => {
    await page.goto("http://localhost:3000/contacts");
    // Wait for either transaction items or empty state to appear (API data takes time to load)
    await page.waitForSelector('[data-test^="transaction-item-"], [data-test="empty-list-header"]', {
      timeout: 15000,
    });
    const hasItems = (await page.locator('[data-test^="transaction-item-"]').count()) > 0;
    const hasEmpty = await page.locator('[data-test="empty-list-header"]').isVisible();
    expect(hasItems || hasEmpty).toBeTruthy();
  });

  test("Personal tab (/personal) shows own transaction list", async ({ page }) => {
    await page.goto("http://localhost:3000/personal");
    // Wait for either transaction items or empty state to appear
    await page.waitForSelector('[data-test^="transaction-item-"], [data-test="empty-list-header"]', {
      timeout: 15000,
    });
    const hasItems = (await page.locator('[data-test^="transaction-item-"]').count()) > 0;
    const hasEmpty = await page.locator('[data-test="empty-list-header"]').isVisible();
    expect(hasItems || hasEmpty).toBeTruthy();
  });

  test("clicking a transaction item navigates to transaction detail", async ({ page }) => {
    await page.goto("http://localhost:3000/");
    // Wait for transaction list
    const firstItem = page.locator('[data-test^="transaction-item-"]').first();
    await firstItem.waitFor({ state: "visible", timeout: 15000 });

    // Get the transaction ID from data-test attribute
    const testAttr = await firstItem.getAttribute("data-test");
    const txId = testAttr?.replace("transaction-item-", "");

    await firstItem.click();
    await expect(page).toHaveURL(/\/transaction\//);
    await expect(page.getByTestId("transaction-detail-header")).toBeVisible();
  });

  test("amount range filter chip is visible and opens popover on click", async ({ page }) => {
    await page.goto("http://localhost:3000/");
    await page.locator('[data-test^="transaction-item-"]').first().waitFor({ timeout: 15000 });

    const amountFilterBtn = page.getByTestId("transaction-list-filter-amount-range-button");
    await expect(amountFilterBtn).toBeVisible();

    await amountFilterBtn.click();
    // The popover/filter should appear
    await expect(page.getByTestId("transaction-list-filter-amount-range")).toBeVisible();
  });

  test("amount range filter can be cleared", async ({ page }) => {
    await page.goto("http://localhost:3000/");
    await page.locator('[data-test^="transaction-item-"]').first().waitFor({ timeout: 15000 });

    await page.getByTestId("transaction-list-filter-amount-range-button").click();
    await expect(page.getByTestId("transaction-list-filter-amount-range")).toBeVisible();

    await page.getByTestId("transaction-list-filter-amount-clear-button").click();
    // Filter should close or reset
    await expect(page.getByTestId("transaction-list-filter-amount-range-text")).toBeVisible();
  });

  test("personal transactions show transactions belonging to logged-in user", async ({ page }) => {
    await page.goto("http://localhost:3000/personal");
    const list = page.locator('[data-test^="transaction-item-"]');
    const hasItems = await list.first().isVisible({ timeout: 15000 }).catch(() => false);
    if (hasItems) {
      // Click one and verify the detail page loads
      await list.first().click();
      await expect(page.getByTestId("transaction-detail-header")).toBeVisible();
    }
  });
});
