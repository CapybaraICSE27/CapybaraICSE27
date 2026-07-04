import { test, expect } from "@playwright/test";
import { loginViaUi, dismissOnboardingIfPresent } from "./helpers/auth";

test.describe("Navigation", () => {
  test.beforeEach(async ({ page }) => {
    await loginViaUi(page);
    await dismissOnboardingIfPresent(page);
  });

  test("shows app name/logo in top nav bar", async ({ page }) => {
    await expect(page.getByTestId("app-name-logo")).toBeVisible();
  });

  test("shows New Transaction button in top nav bar", async ({ page }) => {
    await expect(page.getByTestId("nav-top-new-transaction")).toBeVisible();
  });

  test("New Transaction button navigates to /transaction/new", async ({ page }) => {
    await page.getByTestId("nav-top-new-transaction").click();
    await expect(page).toHaveURL(/\/transaction\/new/);
  });

  test("notifications link is visible in top nav", async ({ page }) => {
    await expect(page.getByTestId("nav-top-notifications-link")).toBeVisible();
  });

  test("notifications link navigates to /notifications", async ({ page }) => {
    await page.getByTestId("nav-top-notifications-link").click();
    await expect(page).toHaveURL(/\/notifications/);
  });

  test("side nav shows user full name, username, and balance", async ({ page }) => {
    await expect(page.getByTestId("sidenav-user-full-name")).toBeVisible();
    await expect(page.getByTestId("sidenav-username")).toBeVisible();
    await expect(page.getByTestId("sidenav-user-balance")).toBeVisible();
  });

  test("side nav Home link is present and points to /", async ({ page }) => {
    const homeLink = page.getByTestId("sidenav-home");
    await expect(homeLink).toBeVisible();
    await homeLink.click();
    await expect(page).toHaveURL(/^http:\/\/localhost:3000\/?$/);
  });

  test("side nav My Account link navigates to /user/settings", async ({ page }) => {
    await page.getByTestId("sidenav-user-settings").click();
    await expect(page).toHaveURL(/\/user\/settings/);
  });

  test("side nav Bank Accounts link navigates to /bankaccounts", async ({ page }) => {
    await page.getByTestId("sidenav-bankaccounts").click();
    await expect(page).toHaveURL(/\/bankaccounts/);
  });

  test("side nav Notifications link navigates to /notifications", async ({ page }) => {
    await page.getByTestId("sidenav-notifications").click();
    await expect(page).toHaveURL(/\/notifications/);
  });

  test("side nav Logout signs out and redirects to signin", async ({ page }) => {
    await page.getByTestId("sidenav-signout").click();
    await expect(page).toHaveURL(/\/signin/, { timeout: 10000 });
  });

  test("transaction tabs show Everyone, Friends, Mine tabs on home page", async ({ page }) => {
    await page.goto("http://localhost:3000/");
    await expect(page.getByTestId("nav-transaction-tabs")).toBeVisible();
    await expect(page.getByTestId("nav-public-tab")).toBeVisible();
    await expect(page.getByTestId("nav-contacts-tab")).toBeVisible();
    await expect(page.getByTestId("nav-personal-tab")).toBeVisible();
  });

  test("Friends tab navigates to /contacts", async ({ page }) => {
    await page.goto("http://localhost:3000/");
    await page.getByTestId("nav-contacts-tab").click();
    await expect(page).toHaveURL(/\/contacts/);
  });

  test("Mine tab navigates to /personal", async ({ page }) => {
    await page.goto("http://localhost:3000/");
    await page.getByTestId("nav-personal-tab").click();
    await expect(page).toHaveURL(/\/personal/);
  });

  test("Everyone tab is active and navigates to / or /public", async ({ page }) => {
    await page.goto("http://localhost:3000/contacts");
    await page.getByTestId("nav-public-tab").click();
    // Should navigate to / or /public
    await expect(page).toHaveURL(/localhost:3000\/?(?:public)?$/);
  });

  test("sidenav toggle button is visible", async ({ page }) => {
    await expect(page.getByTestId("sidenav-toggle")).toBeVisible();
  });
});
