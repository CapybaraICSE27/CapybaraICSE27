/**
 * Auth flows: login page, signup page.
 *
 * KEY CONSTRAINT: authProvider.ts has a module-level
 *   localStorage.setItem('user', JSON.stringify(DEFAULT_USER))
 * that runs on every fresh page load, auto-authenticating the user.
 * To reach the login form we must first load the app (so the module caches),
 * then perform a real logout through the UI.  After the SPA logout the module is
 * already in memory so that one-time setItem never fires again.
 *
 * Signup page: the fakerest backend is always "initialized" (has users), so
 * SignupPage shows LoginSkeleton then redirects away.  The form is unreachable.
 * We verify that the form fields never appear rather than testing the redirect.
 */
import { test, expect } from '@playwright/test';
import { gotoLogin, gotoSignup, waitForAppReady } from './helpers';

test.describe('Login page', () => {
    test('renders email and password inputs', async ({ page }) => {
        await gotoLogin(page);
        await expect(page.locator('input[name="email"]')).toBeVisible();
        await expect(page.locator('input[name="password"]')).toBeVisible();
    });

    test('renders Sign in button', async ({ page }) => {
        await gotoLogin(page);
        await expect(
            page.getByRole('button', { name: /sign in/i })
        ).toBeVisible();
    });

    test('has Forgot your password link', async ({ page }) => {
        await gotoLogin(page);
        await expect(page.getByText(/forgot your password/i)).toBeVisible();
    });

    test('shows validation errors when required fields are empty', async ({
        page,
    }) => {
        await gotoLogin(page);
        // Click sign in without filling the form
        await page.getByRole('button', { name: /sign in/i }).click();
        // React-admin validates required fields before calling authProvider.login
        await expect(page.getByText(/required/i).first()).toBeVisible({
            timeout: 5_000,
        });
    });

    test('can log in with default credentials and reach the dashboard', async ({
        page,
    }) => {
        await gotoLogin(page);
        // The authProvider looks up the email in the fakerest sales list
        await page.locator('input[name="email"]').fill('janedoe@atomic.dev');
        await page.locator('input[name="password"]').fill('demo');
        await page.getByRole('button', { name: /sign in/i }).click();
        // After login react-admin redirects to the default route (/)
        await page.waitForURL('**/', { timeout: 15_000 });
        await expect(
            page.getByRole('tab', { name: /dashboard/i })
        ).toBeVisible();
    });
});

test.describe('Signup page', () => {
    /**
     * With fakerest the system is always "initialized" (has users).
     * SignupPage shows LoginSkeleton while loading, then redirects to /login
     * (and from there to "/" since the user is authenticated).
     * The signup form fields are NEVER rendered in this environment.
     */
    test('signup form is not shown when system is already initialized', async ({
        page,
    }) => {
        await page.goto('/sign-up');
        await waitForAppReady(page);
        // The signup form inputs should never appear for an initialized system –
        // the page either shows LoginSkeleton or has redirected away.
        // not.toBeVisible() passes immediately when the element is absent.
        await expect(page.locator('input[name="first_name"]')).not.toBeVisible({
            timeout: 5_000,
        });
    });
});
