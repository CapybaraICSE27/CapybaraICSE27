import { test, expect } from "@playwright/test";
import { setupApiProxy, getInput } from "./helpers/auth";

const BASE_URL = "http://localhost:3000";

/**
 * Sign up a brand-new user and return their credentials.
 * Uses the API proxy to ensure requests hit the correct backend port.
 * Uses getInput() helper to fill MUI TextField wrapper elements.
 */
async function signUpNewUser(page: any): Promise<{ username: string; password: string }> {
  const username = `pwtest_${Date.now()}`;
  const password = "password123";

  await setupApiProxy(page);
  await page.goto(`${BASE_URL}/signup`);
  await getInput(page, "signup-first-name").fill("PW");
  await getInput(page, "signup-last-name").fill("Tester");
  await getInput(page, "signup-username").fill(username);
  await getInput(page, "signup-password").fill(password);
  await getInput(page, "signup-confirmPassword").fill(password);
  await page.getByTestId("signup-submit").click();

  // After signup, redirected to signin
  await expect(page).toHaveURL(/\/signin/, { timeout: 10000 });

  return { username, password };
}

test.describe("User Onboarding", () => {
  test("new user sees onboarding dialog after first login", async ({ page }) => {
    const { username, password } = await signUpNewUser(page);

    // Sign in with new user (proxy already set up, use getInput for MUI TextFields)
    await getInput(page, "signin-username").fill(username);
    await getInput(page, "signin-password").fill(password);
    await page.getByTestId("signin-submit").click();

    // The onboarding dialog should appear
    await expect(page.getByTestId("user-onboarding-dialog")).toBeVisible({ timeout: 15000 });
    await expect(page.getByTestId("user-onboarding-dialog-title")).toHaveText(
      /Get Started with Real World App/i
    );
  });

  test("onboarding step 1 has next button", async ({ page }) => {
    const { username, password } = await signUpNewUser(page);

    await getInput(page, "signin-username").fill(username);
    await getInput(page, "signin-password").fill(password);
    await page.getByTestId("signin-submit").click();

    await page.getByTestId("user-onboarding-dialog").waitFor({ state: "visible", timeout: 15000 });
    await expect(page.getByTestId("user-onboarding-next")).toBeVisible();
  });

  test("clicking next on step 1 goes to bank account creation step", async ({ page }) => {
    const { username, password } = await signUpNewUser(page);

    await getInput(page, "signin-username").fill(username);
    await getInput(page, "signin-password").fill(password);
    await page.getByTestId("signin-submit").click();

    await page.getByTestId("user-onboarding-dialog").waitFor({ state: "visible", timeout: 15000 });
    await page.getByTestId("user-onboarding-next").click();

    // Step 2 should show bank account form
    await expect(page.getByTestId("bankaccount-form")).toBeVisible({ timeout: 10000 });
    await expect(page.getByTestId("user-onboarding-dialog-title")).toHaveText(
      /Create Bank Account/i
    );
  });

  test("can complete full onboarding flow", async ({ page }) => {
    const { username, password } = await signUpNewUser(page);

    await getInput(page, "signin-username").fill(username);
    await getInput(page, "signin-password").fill(password);
    await page.getByTestId("signin-submit").click();

    await page.getByTestId("user-onboarding-dialog").waitFor({ state: "visible", timeout: 15000 });

    // Step 1: click Next
    await page.getByTestId("user-onboarding-next").click();

    // Step 2: fill bank account form (MUI TextFields, use inner input)
    await page.getByTestId("bankaccount-form").waitFor({ state: "visible", timeout: 10000 });
    await page.locator('[data-test="bankaccount-bankName-input"] input').fill("Onboarding Bank");
    await page.locator('[data-test="bankaccount-routingNumber-input"] input').fill("123456789");
    await page.locator('[data-test="bankaccount-accountNumber-input"] input').fill("987654321");
    await page.getByTestId("bankaccount-submit").click();

    // Step 3: finished screen
    await expect(page.getByTestId("user-onboarding-dialog-title")).toHaveText(/Finished/i, {
      timeout: 10000,
    });
    await expect(page.getByTestId("user-onboarding-next")).toBeVisible();

    // Click Done
    await page.getByTestId("user-onboarding-next").click();

    // Dialog should close
    await expect(page.getByTestId("user-onboarding-dialog")).not.toBeVisible({ timeout: 10000 });
  });

  test("onboarding logout button exists", async ({ page }) => {
    const { username, password } = await signUpNewUser(page);

    await getInput(page, "signin-username").fill(username);
    await getInput(page, "signin-password").fill(password);
    await page.getByTestId("signin-submit").click();

    await page.getByTestId("user-onboarding-dialog").waitFor({ state: "visible", timeout: 15000 });
    await expect(page.getByTestId("user-onboarding-logout")).toBeVisible();
  });
});
