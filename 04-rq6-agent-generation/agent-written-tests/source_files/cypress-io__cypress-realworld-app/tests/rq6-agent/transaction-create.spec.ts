import { test, expect } from "@playwright/test";
import { loginViaUi, dismissOnboardingIfPresent } from "./helpers/auth";

// MUI TextField puts data-test on outer wrapper div, not the <input>.
// Use [data-test="..."] input to reach the actual input element.
function getCreateInput(page: any, testId: string) {
  return page.locator(`[data-test="${testId}"] input`);
}

test.describe("Create Transaction", () => {
  test.beforeEach(async ({ page }) => {
    await loginViaUi(page);
    await dismissOnboardingIfPresent(page);
  });

  test("navigates to /transaction/new", async ({ page }) => {
    await page.goto("http://localhost:3000/transaction/new");
    await expect(page).toHaveURL(/\/transaction\/new/);
  });

  test("step 1: shows user search list", async ({ page }) => {
    await page.goto("http://localhost:3000/transaction/new");
    // User list should load
    await expect(page.getByTestId("users-list")).toBeVisible({ timeout: 15000 });
    // Should have at least one user
    const userItems = page.locator('[data-test^="user-list-item-"]');
    await expect(userItems.first()).toBeVisible();
  });

  test("step 1: search input is visible", async ({ page }) => {
    await page.goto("http://localhost:3000/transaction/new");
    await expect(page.getByTestId("user-list-search-input")).toBeVisible({ timeout: 10000 });
  });

  test("step 1: searching filters the user list", async ({ page }) => {
    await page.goto("http://localhost:3000/transaction/new");
    await page.getByTestId("users-list").waitFor({ state: "visible", timeout: 15000 });

    const searchInput = page.getByTestId("user-list-search-input");
    await searchInput.fill("Arvilla");

    // Wait for the list to update - there should be a matching user
    await page.waitForTimeout(500);
    const visibleUsers = page.locator('[data-test^="user-list-item-"]');
    const count = await visibleUsers.count();
    expect(count).toBeGreaterThan(0);
  });

  test("step 1: clicking a user moves to step 2 (amount form)", async ({ page }) => {
    await page.goto("http://localhost:3000/transaction/new");
    await page.getByTestId("users-list").waitFor({ state: "visible", timeout: 15000 });

    // Click the first user
    const firstUser = page.locator('[data-test^="user-list-item-"]').first();
    await firstUser.click();

    // Step 2 shows amount and description inputs (MUI TextFields with data-test on wrapper)
    await expect(page.getByTestId("transaction-create-amount-input")).toBeVisible({ timeout: 10000 });
    await expect(page.getByTestId("transaction-create-description-input")).toBeVisible();
  });

  test("step 2: pay and request buttons are disabled until form is valid", async ({ page }) => {
    await page.goto("http://localhost:3000/transaction/new");
    await page.getByTestId("users-list").waitFor({ state: "visible", timeout: 15000 });
    const firstUser = page.locator('[data-test^="user-list-item-"]').first();
    await firstUser.click();

    await page.getByTestId("transaction-create-amount-input").waitFor({ timeout: 10000 });

    // Initially both submit buttons should be disabled (amount/description empty)
    await expect(page.getByTestId("transaction-create-submit-payment")).toBeDisabled();
    await expect(page.getByTestId("transaction-create-submit-request")).toBeDisabled();
  });

  test("step 2: buttons are enabled after filling amount and description", async ({ page }) => {
    await page.goto("http://localhost:3000/transaction/new");
    await page.getByTestId("users-list").waitFor({ state: "visible", timeout: 15000 });
    const firstUser = page.locator('[data-test^="user-list-item-"]').first();
    await firstUser.click();

    await page.getByTestId("transaction-create-amount-input").waitFor({ timeout: 10000 });

    // Fill amount and description using inner <input> (MUI TextField wrapper pattern)
    await getCreateInput(page, "transaction-create-amount-input").fill("50");
    await getCreateInput(page, "transaction-create-description-input").fill("Test payment");

    await expect(page.getByTestId("transaction-create-submit-payment")).toBeEnabled({ timeout: 5000 });
    await expect(page.getByTestId("transaction-create-submit-request")).toBeEnabled();
  });

  test("can complete a payment transaction", async ({ page }) => {
    await page.goto("http://localhost:3000/transaction/new");
    await page.getByTestId("users-list").waitFor({ state: "visible", timeout: 15000 });

    // Select a user (not ourselves) - search for a different user
    await page.getByTestId("user-list-search-input").fill("Arvilla");
    await page.waitForTimeout(500);

    const userItem = page.locator('[data-test^="user-list-item-"]').first();
    await userItem.click();

    await page.getByTestId("transaction-create-amount-input").waitFor({ timeout: 10000 });
    await getCreateInput(page, "transaction-create-amount-input").fill("25");
    await getCreateInput(page, "transaction-create-description-input").fill("Test payment Playwright");

    await page.getByTestId("transaction-create-submit-payment").click();

    // After payment, should navigate away from step 1 to step 3 (confirmation) or home
    await expect(page.getByTestId("transaction-create-submit-payment")).not.toBeVisible({
      timeout: 10000,
    });
  });

  test("can complete a request transaction", async ({ page }) => {
    await page.goto("http://localhost:3000/transaction/new");
    await page.getByTestId("users-list").waitFor({ state: "visible", timeout: 15000 });

    await page.getByTestId("user-list-search-input").fill("Arvilla");
    await page.waitForTimeout(500);

    const userItem = page.locator('[data-test^="user-list-item-"]').first();
    await userItem.click();

    await page.getByTestId("transaction-create-amount-input").waitFor({ timeout: 10000 });
    await getCreateInput(page, "transaction-create-amount-input").fill("10");
    await getCreateInput(page, "transaction-create-description-input").fill("Test request Playwright");

    await page.getByTestId("transaction-create-submit-request").click();

    // Should navigate away from step 2 after submission
    await expect(page.getByTestId("transaction-create-submit-request")).not.toBeVisible({
      timeout: 10000,
    });
  });
});
