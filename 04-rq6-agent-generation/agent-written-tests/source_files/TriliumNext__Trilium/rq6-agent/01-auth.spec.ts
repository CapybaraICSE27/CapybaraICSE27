/**
 * E2E tests for authentication pages:
 * - Login page (/login)
 * - Set-password page (/set-password) - server rendered
 * - Logout flow
 * - Unauthenticated redirect
 */
import { test, expect } from "@playwright/test";
import { PASSWORD, login } from "./helpers";

test.describe("Login page", () => {
    test("shows login form with required fields", async ({ page }) => {
        await page.goto("/login", { waitUntil: "networkidle", timeout: 30_000 });

        await expect(page).toHaveTitle(/login/i);
        await expect(page.locator("#password")).toBeVisible();
        await expect(page.getByRole("button", { name: "Login" })).toBeVisible();
        await expect(page.getByLabel(/remember me/i)).toBeVisible();
    });

    test("successful login redirects to main app", async ({ page }) => {
        await page.goto("/login", { waitUntil: "networkidle", timeout: 30_000 });
        await page.locator("#password").fill(PASSWORD);
        await page.getByRole("button", { name: "Login" }).click();

        await page.waitForURL("/", { timeout: 30_000 });
        await expect(page.locator(".tree-wrapper")).toBeVisible({ timeout: 30_000 });
    });

    test("wrong password shows error message", async ({ page }) => {
        await page.goto("/login", { waitUntil: "networkidle", timeout: 30_000 });
        await page.locator("#password").fill("wrongpassword");
        await page.getByRole("button", { name: "Login" }).click();

        // Should stay on login page
        await page.waitForTimeout(2000);
        expect(page.url()).toContain("/login");

        // Check for error message - the app uses .alert-warning
        const errorMsg = page.locator(".alert-warning, .alert-danger, .alert");
        await expect(errorMsg.first()).toBeVisible({ timeout: 5_000 });
        const text = await errorMsg.first().innerText();
        expect(text).toMatch(/incorrect|invalid|wrong|failed/i);
    });

    test("empty password shows validation or stays on page", async ({ page }) => {
        await page.goto("/login", { waitUntil: "networkidle", timeout: 30_000 });
        await page.getByRole("button", { name: "Login" }).click();
        await page.waitForTimeout(1500);
        // Should remain on login page
        expect(page.url()).toContain("/login");
    });

    test("unauthenticated access to root redirects appropriately", async ({ page }) => {
        // Access bootstrap without being logged in - should redirect or show error
        await page.goto("/bootstrap", { waitUntil: "networkidle", timeout: 30_000 });
        const body = await page.locator("body").innerText();
        const isLoginPage = page.url().includes("/login") || body.includes("Login") || body.includes("password");
        expect(isLoginPage).toBeTruthy();
    });
});

test.describe("Logout flow", () => {
    test("can log out from the app", async ({ page }) => {
        await login(page);

        // Get CSRF token for authenticated API calls
        const csrfToken = await page.evaluate(() => (window as any).glob?.csrfToken ?? "");

        if (csrfToken) {
            // Use the logout endpoint
            await page.request.post("/logout", {
                headers: { "x-csrf-token": csrfToken },
            });
        }

        // Navigate away and check redirect
        await page.goto("/", { waitUntil: "networkidle", timeout: 15_000 });
        await page.waitForTimeout(1000);

        // After logout, should be redirected to login
        const url = page.url();
        const body = await page.locator("body").innerText();
        const isLoggedOut = url.includes("/login") || body.includes("Login") || body.includes("password");
        expect(isLoggedOut).toBeTruthy();
    });
});
