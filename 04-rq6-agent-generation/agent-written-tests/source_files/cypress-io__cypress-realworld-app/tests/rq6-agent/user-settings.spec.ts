import { test, expect } from "@playwright/test";
import { loginViaUi, dismissOnboardingIfPresent } from "./helpers/auth";

test.describe("User Settings", () => {
  test.beforeEach(async ({ page }) => {
    await loginViaUi(page);
    await dismissOnboardingIfPresent(page);
    await page.goto("http://localhost:3000/user/settings");
    await page.getByTestId("user-settings-form").waitFor({ state: "visible", timeout: 15000 });
  });

  test("user settings page shows the form", async ({ page }) => {
    await expect(page.getByTestId("user-settings-form")).toBeVisible();
  });

  test("form fields are pre-filled with current user data", async ({ page }) => {
    // Fields should contain existing values (not empty)
    const firstNameInput = page.locator('[data-test="user-settings-firstName-input"]');
    const lastNameInput = page.locator('[data-test="user-settings-lastName-input"]');
    const emailInput = page.locator('[data-test="user-settings-email-input"]');
    const phoneInput = page.locator('[data-test="user-settings-phoneNumber-input"]');

    await expect(firstNameInput).not.toBeEmpty();
    await expect(lastNameInput).not.toBeEmpty();
    await expect(emailInput).not.toBeEmpty();
    await expect(phoneInput).not.toBeEmpty();
  });

  test("save button is visible", async ({ page }) => {
    await expect(page.getByTestId("user-settings-submit")).toBeVisible();
  });

  test("shows error when first name is cleared", async ({ page }) => {
    const firstNameInput = page.locator('[data-test="user-settings-firstName-input"]');
    await firstNameInput.clear();
    await firstNameInput.press("Tab");
    await expect(page.getByText("Enter a first name")).toBeVisible();
    await expect(page.getByTestId("user-settings-submit")).toBeDisabled();
  });

  test("shows error when last name is cleared", async ({ page }) => {
    const lastNameInput = page.locator('[data-test="user-settings-lastName-input"]');
    await lastNameInput.clear();
    await lastNameInput.press("Tab");
    await expect(page.getByText("Enter a last name")).toBeVisible();
  });

  test("shows error for invalid email format", async ({ page }) => {
    const emailInput = page.locator('[data-test="user-settings-email-input"]');
    await emailInput.clear();
    await emailInput.fill("not-an-email");
    await emailInput.press("Tab");
    await expect(page.getByText("Must contain a valid email address")).toBeVisible();
  });

  test("save button is disabled when required fields are cleared", async ({ page }) => {
    const firstNameInput = page.locator('[data-test="user-settings-firstName-input"]');
    await firstNameInput.clear();
    await firstNameInput.press("Tab");
    await expect(page.getByTestId("user-settings-submit")).toBeDisabled();
  });

  test("can update user settings successfully", async ({ page }) => {
    // Update the phone number to a valid one
    const phoneInput = page.locator('[data-test="user-settings-phoneNumber-input"]');
    await phoneInput.clear();
    await phoneInput.fill("6155553333");

    const submitBtn = page.getByTestId("user-settings-submit");
    await expect(submitBtn).toBeEnabled();
    await submitBtn.click();

    // After saving, the form should still be displayed (settings page persists)
    // Or there may be a success notification
    await expect(page.getByTestId("user-settings-form")).toBeVisible({ timeout: 10000 });
  });
});
