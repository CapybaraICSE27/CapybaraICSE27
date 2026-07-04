/**
 * Tests for public pages: Login, Register, Terms, Privacy, Pricing, Features,
 * Topics, Maintenance, Messages (verified/expired/registered/unsubscribed)
 * No authentication required.
 */
import { test, expect } from "./test-fixtures";

test.describe("Login Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(1000);
  });

  test("shows login form with email field", async ({ page }) => {
    const emailInput = page.getByTestId("email");
    await expect(emailInput).toBeVisible();
    await expect(emailInput).toHaveAttribute("type", "email");
  });

  test("shows page title", async ({ page }) => {
    await expect(page).toHaveTitle(/login/i);
  });

  test("shows Continue button", async ({ page }) => {
    const continueBtn = page.getByRole("button", { name: "Continue" });
    await expect(continueBtn).toBeVisible();
  });

  test("shows Sign in with Google button", async ({ page }) => {
    const googleBtn = page.getByRole("button", { name: /sign in with google/i });
    await expect(googleBtn).toBeVisible();
  });

  test("shows Sign in with Github button", async ({ page }) => {
    const githubBtn = page.getByRole("button", { name: /sign in with github/i });
    await expect(githubBtn).toBeVisible();
  });

  test("shows Welcome Back heading", async ({ page }) => {
    await expect(page.getByText(/welcome back/i)).toBeVisible();
  });

  test("shows cookie banner", async ({ page }) => {
    await expect(page.getByTestId("close-cookie-banner")).toBeVisible();
  });

  test("can dismiss cookie banner", async ({ page }) => {
    const closeBanner = page.getByTestId("close-cookie-banner");
    await expect(closeBanner).toBeVisible();
    await closeBanner.click();
    await expect(
      page.getByText(/we use cookies to enhance your user experience/i)
    ).not.toBeVisible();
  });

  test("shows link to create account", async ({ page }) => {
    await expect(page.getByRole("link", { name: /create one/i })).toBeVisible();
  });

  test("email input accepts input", async ({ page }) => {
    const emailInput = page.getByTestId("email");
    await emailInput.fill("test@example.com");
    await expect(emailInput).toHaveValue("test@example.com");
  });

  test("shows footer links - Terms and Privacy", async ({ page }) => {
    const termsLink = page.getByRole("link", { name: /terms/i }).first();
    const privacyLink = page.getByRole("link", { name: /privacy/i }).first();
    await expect(termsLink).toBeVisible();
    await expect(privacyLink).toBeVisible();
  });
});

test.describe("Register Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/register");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(1000);
  });

  test("shows Join Letterpad heading", async ({ page }) => {
    await expect(page.getByText(/join letterpad/i)).toBeVisible();
  });

  test("shows page title", async ({ page }) => {
    await expect(page).toHaveTitle(/register/i);
  });

  test("shows email input field", async ({ page }) => {
    await expect(page.getByTestId("email")).toBeVisible();
  });

  test("shows Continue button", async ({ page }) => {
    await expect(page.getByRole("button", { name: /continue/i })).toBeVisible();
  });

  test("shows Sign up with Google button", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /sign up with google/i })
    ).toBeVisible();
  });

  test("shows Sign up with Github button", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /sign up with github/i })
    ).toBeVisible();
  });

  test("shows link to sign in", async ({ page }) => {
    await expect(page.getByRole("link", { name: /sign in/i })).toBeVisible();
  });
});

test.describe("Terms Page", () => {
  test("shows terms of use heading", async ({ page }) => {
    await page.goto("/terms");
    await expect(
      page.getByRole("heading", { name: /terms of use/i })
    ).toBeVisible({ timeout: 10000 });
  });

  test("has correct title", async ({ page }) => {
    await page.goto("/terms");
    await expect(page).toHaveTitle(/terms/i);
  });
});

test.describe("Privacy Page", () => {
  test("shows privacy policy heading", async ({ page }) => {
    await page.goto("/privacy");
    await page.waitForLoadState("domcontentloaded");
    // The heading may say "Privacy Policy" or similar
    const heading = page.locator("h1").first();
    await expect(heading).toBeVisible({ timeout: 10000 });
    const text = await heading.textContent();
    expect(text?.toLowerCase()).toContain("privacy");
  });

  test("has correct title", async ({ page }) => {
    await page.goto("/privacy");
    // Privacy page title is "Letterpad - A blog publishing platform"
    await expect(page).toHaveTitle(/letterpad/i);
  });
});

test.describe("Pricing Page", () => {
  test("loads pricing page", async ({ page }) => {
    await page.goto("/pricing");
    await expect(page).toHaveTitle(/pricing/i);
  });

  test("shows Pricing heading", async ({ page }) => {
    await page.goto("/pricing");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(1000);
    await expect(
      page.getByRole("heading", { name: /pricing/i })
    ).toBeVisible({ timeout: 10000 });
  });

  test("shows Free tier", async ({ page }) => {
    await page.goto("/pricing");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(1500);
    await expect(page.getByText(/free/i).first()).toBeVisible();
  });

  test("shows Pro tier", async ({ page }) => {
    await page.goto("/pricing");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(1500);
    await expect(page.getByText(/pro/i).first()).toBeVisible();
  });
});

test.describe("Features Page", () => {
  test("loads features page", async ({ page }) => {
    await page.goto("/features");
    await expect(page).toHaveTitle(/features/i);
  });

  test("shows main heading", async ({ page }) => {
    await page.goto("/features");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(1500);
    await expect(
      page.getByRole("heading").first()
    ).toBeVisible({ timeout: 10000 });
  });
});

test.describe("Topics Page", () => {
  test("loads topics page", async ({ page }) => {
    await page.goto("/topics");
    await page.waitForLoadState("domcontentloaded");
    await expect(page.locator("body")).toBeVisible();
  });

  test("shows Explore heading", async ({ page }) => {
    await page.goto("/topics");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);
    await expect(
      page.getByRole("heading", { name: /explore/i })
    ).toBeVisible({ timeout: 10000 });
  });
});

test.describe("Maintenance Page", () => {
  test("shows Under Maintenance heading", async ({ page }) => {
    await page.goto("/maintenance");
    await page.waitForLoadState("domcontentloaded");
    await expect(
      page.getByRole("heading", { name: /maintenance/i })
    ).toBeVisible({ timeout: 10000 });
  });

  test("shows maintenance status message", async ({ page }) => {
    await page.goto("/maintenance");
    await page.waitForLoadState("domcontentloaded");
    await expect(
      page.getByText(/system check|back soon|breather/i)
    ).toBeVisible({ timeout: 10000 });
  });

  test("renders maintenance page without redirect", async ({ page }) => {
    await page.goto("/maintenance");
    await expect(page).toHaveURL(/\/maintenance/);
    await expect(page.locator("body")).toBeVisible();
  });
});

test.describe("Message: Email Verified", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/messages/verified");
    await page.waitForLoadState("domcontentloaded");
  });

  test("shows Email Verified heading", async ({ page }) => {
    await expect(
      page.getByRole("heading", { name: /email verified/i })
    ).toBeVisible({ timeout: 10000 });
  });

  test("shows verification success message", async ({ page }) => {
    await expect(
      page.getByText(/successfully verified/i)
    ).toBeVisible({ timeout: 10000 });
  });

  test("shows Proceed to Login button", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /proceed to login/i })
    ).toBeVisible({ timeout: 10000 });
  });
});

test.describe("Message: Link Expired", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/messages/expired");
    await page.waitForLoadState("domcontentloaded");
  });

  test("shows Link Expired heading", async ({ page }) => {
    await expect(
      page.getByRole("heading", { name: /link expired/i })
    ).toBeVisible({ timeout: 10000 });
  });

  test("shows expiry message", async ({ page }) => {
    await expect(
      page.getByText(/token.*expired|expired.*token/i)
    ).toBeVisible({ timeout: 10000 });
  });

  test("shows Proceed to Home button", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /proceed to home/i })
    ).toBeVisible({ timeout: 10000 });
  });
});

test.describe("Message: Registration Success", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/messages/registered");
    await page.waitForLoadState("domcontentloaded");
  });

  test("shows Welcome Aboard heading", async ({ page }) => {
    await expect(
      page.getByRole("heading", { name: /welcome aboard/i })
    ).toBeVisible({ timeout: 10000 });
  });

  test("shows registration success message", async ({ page }) => {
    await expect(
      page.getByText(/registered successfully/i)
    ).toBeVisible({ timeout: 10000 });
  });

  test("shows Proceed to Login button", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /proceed to login/i })
    ).toBeVisible({ timeout: 10000 });
  });
});

test.describe("Message: Unsubscribed", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/messages/unsubscribed");
    await page.waitForLoadState("domcontentloaded");
  });

  test("shows Unsubscribed heading", async ({ page }) => {
    await expect(
      page.getByRole("heading", { name: /unsubscribed/i })
    ).toBeVisible({ timeout: 10000 });
  });

  test("shows unsubscribed message", async ({ page }) => {
    await expect(
      page.getByText(/removed from our system|unsubscribed/i).first()
    ).toBeVisible({ timeout: 10000 });
  });

  test("shows Proceed to Home button", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /proceed to home/i })
    ).toBeVisible({ timeout: 10000 });
  });
});

test.describe("Root redirect", () => {
  test("redirects / to /login when not authenticated", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/login/);
  });
});

test.describe("Cookie Banner", () => {
  test("cookie banner appears on login page", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByTestId("close-cookie-banner")).toBeVisible();
  });

  test("close button dismisses cookie banner", async ({ page }) => {
    await page.goto("/login");
    const closeBtn = page.getByTestId("close-cookie-banner");
    await closeBtn.click();
    await expect(
      page.getByText(/we use cookies to enhance/i)
    ).not.toBeVisible();
  });
});
