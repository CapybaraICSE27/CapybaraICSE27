import { test, expect } from "@playwright/test";
import { getInput, setupApiProxy } from "./helpers/auth";

const BASE_URL = "http://localhost:3000";
const VALID_USER = { username: "Heath93", password: "s3cret" };

// MUI TextField places data-test on the outer div wrapper, not on <input>.
// Use getInput() helper which descends into the actual <input> element.

test.describe("Sign In Page", () => {
  test.beforeEach(async ({ page }) => {
    await setupApiProxy(page);
    await page.goto(`${BASE_URL}/signin`);
  });

  test("displays sign in form with all required elements", async ({ page }) => {
    await expect(page.getByTestId("signin-username")).toBeVisible();
    await expect(page.getByTestId("signin-password")).toBeVisible();
    await expect(page.getByTestId("signin-remember-me")).toBeVisible();
    await expect(page.getByTestId("signin-submit")).toBeVisible();
  });

  test("sign-in link to signup page is visible", async ({ page }) => {
    await expect(page.getByTestId("signup")).toBeVisible();
  });

  test("shows validation error for short password", async ({ page }) => {
    await getInput(page, "signin-username").fill("Heath93");
    await getInput(page, "signin-password").fill("abc");
    // Tab away to trigger blur/touched state
    await getInput(page, "signin-password").press("Tab");
    await expect(page.getByText("Password must contain at least 4 characters")).toBeVisible();
  });

  test("shows error message for invalid credentials", async ({ page }) => {
    await getInput(page, "signin-username").fill("Heath93");
    await getInput(page, "signin-password").fill("wrongpassword");
    await page.getByTestId("signin-submit").click();
    await expect(page.getByTestId("signin-error")).toBeVisible({ timeout: 10000 });
  });

  test("sign-up link has correct href and signup page is accessible", async ({ page }) => {
    // Verify the signup link exists with correct href
    const signupLink = page.locator('a[href="/signup"]');
    await expect(signupLink).toBeVisible();
    await expect(signupLink).toHaveAttribute("href", "/signup");
    // Verify signup page is accessible
    await page.goto(`${BASE_URL}/signup`);
    await expect(page.getByTestId("signup-title")).toBeVisible();
  });

  test("successfully signs in with valid credentials", async ({ page }) => {
    await getInput(page, "signin-username").fill(VALID_USER.username);
    await getInput(page, "signin-password").fill(VALID_USER.password);
    await page.getByTestId("signin-submit").click();
    // After successful login, sidenav appears
    await expect(page.getByTestId("sidenav")).toBeVisible({ timeout: 15000 });
  });

  test("unauthenticated access to protected route redirects to signin", async ({ page }) => {
    await page.goto(`${BASE_URL}/`);
    await expect(page).toHaveURL(/\/signin/);
  });

  test("remember me checkbox is present on sign-in form", async ({ page }) => {
    await expect(page.getByTestId("signin-remember-me")).toBeVisible();
  });
});

test.describe("Sign Up Page", () => {
  test.beforeEach(async ({ page }) => {
    await setupApiProxy(page);
    await page.goto(`${BASE_URL}/signup`);
  });

  test("displays sign up form with all required fields", async ({ page }) => {
    await expect(page.getByTestId("signup-title")).toBeVisible();
    await expect(page.getByTestId("signup-first-name")).toBeVisible();
    await expect(page.getByTestId("signup-last-name")).toBeVisible();
    await expect(page.getByTestId("signup-username")).toBeVisible();
    await expect(page.getByTestId("signup-password")).toBeVisible();
    await expect(page.getByTestId("signup-confirmPassword")).toBeVisible();
    await expect(page.getByTestId("signup-submit")).toBeVisible();
  });

  test("shows validation error when passwords do not match", async ({ page }) => {
    await getInput(page, "signup-first-name").fill("Test");
    await getInput(page, "signup-last-name").fill("User");
    await getInput(page, "signup-username").fill("testuser_unique123");
    await getInput(page, "signup-password").fill("password1");
    await getInput(page, "signup-confirmPassword").fill("password2");
    await getInput(page, "signup-confirmPassword").press("Tab");
    await expect(page.getByText("Password does not match")).toBeVisible();
  });

  test("shows required field error when first name is cleared", async ({ page }) => {
    await getInput(page, "signup-first-name").fill("A");
    await getInput(page, "signup-first-name").clear();
    await getInput(page, "signup-first-name").press("Tab");
    await expect(page.getByText("First Name is required")).toBeVisible();
  });

  test("shows error for password shorter than 4 characters", async ({ page }) => {
    await getInput(page, "signup-password").fill("abc");
    await getInput(page, "signup-password").press("Tab");
    await expect(page.getByText("Password must contain at least 4 characters")).toBeVisible();
  });

  test("submit button is disabled when passwords do not match", async ({ page }) => {
    await getInput(page, "signup-first-name").fill("Test");
    await getInput(page, "signup-last-name").fill("User");
    await getInput(page, "signup-username").fill("testuser_abc");
    await getInput(page, "signup-password").fill("password1");
    await getInput(page, "signup-confirmPassword").fill("differentpassword");
    await getInput(page, "signup-confirmPassword").press("Tab");
    await expect(page.getByTestId("signup-submit")).toBeDisabled();
  });

  test("sign-in link has correct href and signin page is accessible", async ({ page }) => {
    // Verify the signin link exists with correct href
    const signinLink = page.locator('a[href="/signin"]');
    await expect(signinLink).toBeVisible();
    await expect(signinLink).toHaveAttribute("href", "/signin");
    // Verify signin page is accessible
    await page.goto(`${BASE_URL}/signin`);
    await expect(page.getByTestId("signin-submit")).toBeVisible();
  });

  test("successfully creates a new account and redirects to signin", async ({ page }) => {
    const uniqueUsername = `testuser_${Date.now()}`;
    await getInput(page, "signup-first-name").fill("New");
    await getInput(page, "signup-last-name").fill("User");
    await getInput(page, "signup-username").fill(uniqueUsername);
    await getInput(page, "signup-password").fill("password123");
    await getInput(page, "signup-confirmPassword").fill("password123");

    await expect(page.getByTestId("signup-submit")).toBeEnabled();
    await page.getByTestId("signup-submit").click();

    // After signup, the auth machine calls history.push("/signin")
    await expect(page).toHaveURL(/\/signin/, { timeout: 10000 });
  });
});
