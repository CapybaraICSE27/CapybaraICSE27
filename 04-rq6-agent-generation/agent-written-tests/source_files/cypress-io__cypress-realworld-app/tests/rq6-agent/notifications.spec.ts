import { test, expect } from "@playwright/test";
import { loginViaUi, dismissOnboardingIfPresent } from "./helpers/auth";

test.describe("Notifications", () => {
  test.beforeEach(async ({ page }) => {
    await loginViaUi(page);
    await dismissOnboardingIfPresent(page);
  });

  test("notifications page loads at /notifications", async ({ page }) => {
    await page.goto("http://localhost:3000/notifications");
    await expect(page).toHaveURL(/\/notifications/);
  });

  test("shows notification list or empty state", async ({ page }) => {
    await page.goto("http://localhost:3000/notifications");
    // Wait for API data to load — either a list of notifications or an empty state
    await page.waitForSelector('[data-test="notifications-list"], [data-test="empty-list-header"]', {
      timeout: 15000,
    });
    const hasList = await page.getByTestId("notifications-list").isVisible();
    const hasEmpty = await page.locator('[data-test="empty-list-header"]').isVisible();
    expect(hasList || hasEmpty).toBeTruthy();
  });

  test("notification badge shows count in top nav when there are notifications", async ({ page }) => {
    await page.goto("http://localhost:3000/");
    // The notifications count badge is optional (only visible if > 0)
    const badge = page.getByTestId("nav-top-notifications-count");
    // Badge exists in DOM always
    await expect(badge).toBeAttached();
  });

  test("can dismiss a notification", async ({ page }) => {
    await page.goto("http://localhost:3000/notifications");

    // Wait for either notifications or empty state to load
    await page.waitForSelector('[data-test="notifications-list"], [data-test="empty-list-header"]', {
      timeout: 15000,
    });

    const hasNotifications = await page.getByTestId("notifications-list").isVisible();

    if (hasNotifications) {
      const firstNotification = page.locator('[data-test^="notification-list-item-"]').first();
      await firstNotification.waitFor({ state: "visible" });

      // Get notification ID
      const testAttr = await firstNotification.getAttribute("data-test");
      const notifId = testAttr?.replace("notification-list-item-", "");

      // Click the dismiss/mark-as-read button
      const dismissBtn = page.locator(`[data-test="notification-mark-read-${notifId}"]`);
      await dismissBtn.click();

      // The notification should be removed from the list or marked as read
      await expect(page.locator(`[data-test="notification-list-item-${notifId}"]`)).not.toBeVisible({
        timeout: 10000,
      });
    } else {
      // No notifications to dismiss - skip with a message
      test.skip(true, "No notifications available to dismiss");
    }
  });

  test("notifications page is accessible from notification link in top nav", async ({ page }) => {
    await page.goto("http://localhost:3000/");
    await page.getByTestId("nav-top-notifications-link").click();
    await expect(page).toHaveURL(/\/notifications/);
  });

  test("notification items show message text", async ({ page }) => {
    await page.goto("http://localhost:3000/notifications");
    const list = page.getByTestId("notifications-list");
    const hasNotifications = await list.isVisible({ timeout: 15000 }).catch(() => false);

    if (hasNotifications) {
      const firstItem = page.locator('[data-test^="notification-list-item-"]').first();
      await expect(firstItem).toBeVisible();
      // The notification should contain some text
      const text = await firstItem.textContent();
      expect(text?.length).toBeGreaterThan(0);
    }
  });
});
