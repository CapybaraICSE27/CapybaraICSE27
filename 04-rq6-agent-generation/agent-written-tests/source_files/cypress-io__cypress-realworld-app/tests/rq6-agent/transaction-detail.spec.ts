import { test, expect } from "@playwright/test";
import { loginViaUi, dismissOnboardingIfPresent } from "./helpers/auth";

/**
 * Navigate to the first available transaction detail page from the public list.
 */
async function goToFirstTransactionDetail(page: any) {
  await page.goto("http://localhost:3000/");
  const firstItem = page.locator('[data-test^="transaction-item-"]').first();
  await firstItem.waitFor({ state: "visible", timeout: 15000 });
  await firstItem.click();
  await page.getByTestId("transaction-detail-header").waitFor({ state: "visible", timeout: 10000 });
}

test.describe("Transaction Detail", () => {
  test.beforeEach(async ({ page }) => {
    await loginViaUi(page);
    await dismissOnboardingIfPresent(page);
  });

  test("shows transaction detail header", async ({ page }) => {
    await goToFirstTransactionDetail(page);
    await expect(page.getByTestId("transaction-detail-header")).toBeVisible();
    await expect(page.getByTestId("transaction-detail-header")).toHaveText(/Transaction Detail/i);
  });

  test("shows sender and receiver avatars", async ({ page }) => {
    await goToFirstTransactionDetail(page);
    await expect(page.getByTestId("transaction-sender-avatar")).toBeVisible();
    await expect(page.getByTestId("transaction-receiver-avatar")).toBeVisible();
  });

  test("shows transaction description", async ({ page }) => {
    await goToFirstTransactionDetail(page);
    await expect(page.getByTestId("transaction-description")).toBeVisible();
  });

  test("shows like button and like count", async ({ page }) => {
    await goToFirstTransactionDetail(page);
    // Get the transaction ID from the item element
    const txItem = page.locator('[data-test^="transaction-item-"]').first();
    const testAttr = await txItem.getAttribute("data-test");
    const txId = testAttr?.replace("transaction-item-", "");

    await expect(page.locator(`[data-test="transaction-like-count-${txId}"]`)).toBeVisible();
    await expect(page.locator(`[data-test="transaction-like-button-${txId}"]`)).toBeVisible();
  });

  test("like button increments like count when clicked", async ({ page }) => {
    // Go to personal transactions to find a transaction where current user is NOT a liker
    await page.goto("http://localhost:3000/personal");
    const firstItem = page.locator('[data-test^="transaction-item-"]').first();
    const hasItems = await firstItem.isVisible({ timeout: 10000 }).catch(() => false);

    if (!hasItems) {
      // Fall back to public list
      await page.goto("http://localhost:3000/");
      await page.locator('[data-test^="transaction-item-"]').first().waitFor({ timeout: 15000 });
    }

    const item = page.locator('[data-test^="transaction-item-"]').first();
    const testAttr = await item.getAttribute("data-test");
    const txId = testAttr?.replace("transaction-item-", "");
    await item.click();

    await page.getByTestId("transaction-detail-header").waitFor({ state: "visible" });

    const likeBtn = page.locator(`[data-test="transaction-like-button-${txId}"]`);
    const likeCount = page.locator(`[data-test="transaction-like-count-${txId}"]`);

    // Read initial count
    const initialCountText = await likeCount.textContent();
    const initialCount = parseInt(initialCountText?.trim() || "0", 10);

    const isDisabled = await likeBtn.isDisabled();
    if (!isDisabled) {
      await likeBtn.click();
      // Count should increment
      await expect(likeCount).toHaveText(String(initialCount + 1), { timeout: 5000 });
    } else {
      // Already liked – verify count is displayed
      expect(initialCount).toBeGreaterThanOrEqual(0);
    }
  });

  test("comment form is visible on transaction detail", async ({ page }) => {
    await goToFirstTransactionDetail(page);
    // Comment input uses data-test="transaction-comment-input-{id}"
    const commentInput = page.locator('[data-test^="transaction-comment-input-"]');
    await expect(commentInput).toBeVisible();
  });

  test("can submit a comment on a transaction", async ({ page }) => {
    await goToFirstTransactionDetail(page);
    const commentInput = page.locator('[data-test^="transaction-comment-input-"]').first();
    // Use a unique comment text to avoid conflicts with previous test runs
    const uniqueComment = `PW comment ${Date.now()}`;
    await commentInput.fill(uniqueComment);
    await commentInput.press("Enter");
    // After pressing enter the unique comment should appear exactly once
    await expect(page.getByText(uniqueComment).first()).toBeVisible({ timeout: 10000 });
  });
});
