import { expect, test } from '@playwright/test';
import { mockCoreAPIs } from './helpers/api-mocks';

test.describe('Header Navigation (unauthenticated)', () => {
    test.beforeEach(async ({ page }) => {
        await mockCoreAPIs(page);
        await page.goto('/');
    });

    test('shows Home link in header', async ({ page }) => {
        // Home link exists in the header
        const homeLink = page.locator('header').getByRole('link', { name: /home/i }).first();
        await expect(homeLink).toBeVisible();
    });

    test('shows Sign In link in header', async ({ page }) => {
        const signInLink = page.locator('header').getByRole('link', { name: /sign in/i });
        await expect(signInLink).toBeVisible();
    });

    test('shows Sign Up link in header', async ({ page }) => {
        const signUpLink = page.locator('header').getByRole('link', { name: /sign up/i });
        await expect(signUpLink).toBeVisible();
    });

    test('clicking Sign In navigates to /login', async ({ page }) => {
        const signInLink = page.locator('header').getByRole('link', { name: /sign in/i });
        await signInLink.click();
        await expect(page).toHaveURL('/login');
    });

    test('clicking Sign Up navigates to /register', async ({ page }) => {
        const signUpLink = page.locator('header').getByRole('link', { name: /sign up/i });
        await signUpLink.click();
        await expect(page).toHaveURL('/register');
    });

    test('Home link navigates back to /', async ({ page }) => {
        await page.goto('/terms');
        await page.goBack();
        await expect(page).toHaveURL('/');
    });

    test('shows Hemmelig.app hero heading', async ({ page }) => {
        await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    });

    test('shows hero subtitle text', async ({ page }) => {
        await expect(
            page.getByText(/share secrets securely/i).first()
        ).toBeVisible();
    });
});

test.describe('Footer Navigation', () => {
    test.beforeEach(async ({ page }) => {
        await mockCoreAPIs(page);
        await page.goto('/');
    });

    test('footer has Privacy link', async ({ page }) => {
        const footer = page.locator('footer');
        await expect(footer).toBeVisible();
        await expect(footer.getByRole('link', { name: /privacy/i })).toBeVisible();
    });

    test('footer has Terms link', async ({ page }) => {
        const footer = page.locator('footer');
        await expect(footer.getByRole('link', { name: /terms/i })).toBeVisible();
    });

    test('footer Privacy link navigates to /privacy', async ({ page }) => {
        const footer = page.locator('footer');
        await footer.getByRole('link', { name: /privacy/i }).click();
        await expect(page).toHaveURL('/privacy');
    });

    test('footer Terms link navigates to /terms', async ({ page }) => {
        const footer = page.locator('footer');
        await footer.getByRole('link', { name: /terms/i }).click();
        await expect(page).toHaveURL('/terms');
    });

    test('footer shows Hemmelig tagline', async ({ page }) => {
        // The footer should have a tagline mentioning "secret" in Norwegian
        await expect(page.getByText(/hemmelig.*secret.*norwegian/i).or(
            page.locator('footer').getByText(/secret.*norwegian/i)
        )).toBeVisible();
    });
});

test.describe('Page Navigation Flows', () => {
    test.beforeEach(async ({ page }) => {
        await mockCoreAPIs(page);
    });

    test('can navigate from login to register', async ({ page }) => {
        await page.goto('/login');
        const signUpLink = page.getByRole('link', { name: /sign up/i });
        await expect(signUpLink).toBeVisible();
        await signUpLink.click();
        await expect(page).toHaveURL('/register');
    });

    test('can navigate from register to login', async ({ page }) => {
        await page.goto('/register');
        const signInLink = page.getByRole('link', { name: /sign in/i });
        await expect(signInLink).toBeVisible();
        await signInLink.click();
        await expect(page).toHaveURL('/login');
    });

    test('login page has back to hemmelig link', async ({ page }) => {
        await page.goto('/login');
        const backLink = page.getByRole('link', { name: /back to hemmelig/i });
        await expect(backLink).toBeVisible();
        await backLink.click();
        await expect(page).toHaveURL('/');
    });

    test('register page has back to hemmelig link', async ({ page }) => {
        await page.goto('/register');
        const backLink = page.getByRole('link', { name: /back to hemmelig/i });
        await expect(backLink).toBeVisible();
        await backLink.click();
        await expect(page).toHaveURL('/');
    });

    test('browser title contains Hemmelig', async ({ page }) => {
        await page.goto('/');
        await expect(page).toHaveTitle(/hemmelig/i);
    });
});
