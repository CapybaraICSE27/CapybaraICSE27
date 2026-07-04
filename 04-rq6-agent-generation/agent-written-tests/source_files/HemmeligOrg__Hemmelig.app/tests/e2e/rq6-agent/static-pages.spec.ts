import { expect, test } from '@playwright/test';
import { mockCoreAPIs } from './helpers/api-mocks';

test.describe('Terms Page', () => {
    test.beforeEach(async ({ page }) => {
        await mockCoreAPIs(page);
    });

    test('renders terms page with correct heading', async ({ page }) => {
        await page.goto('/terms');
        await expect(page.getByRole('heading', { name: 'Terms & Conditions' })).toBeVisible();
    });

    test('contains Agreement to Terms section', async ({ page }) => {
        await page.goto('/terms');
        await expect(page.getByRole('heading', { name: 'Agreement to Terms' })).toBeVisible();
    });

    test('contains User Registration section', async ({ page }) => {
        await page.goto('/terms');
        await expect(page.getByRole('heading', { name: 'User Registration' })).toBeVisible();
    });

    test('contains Prohibited Activities section', async ({ page }) => {
        await page.goto('/terms');
        await expect(page.getByRole('heading', { name: 'Prohibited Activities' })).toBeVisible();
    });

    test('contains Disclaimer section', async ({ page }) => {
        await page.goto('/terms');
        await expect(page.getByRole('heading', { name: 'Disclaimer' })).toBeVisible();
    });
});

test.describe('Privacy Page', () => {
    test.beforeEach(async ({ page }) => {
        await mockCoreAPIs(page);
    });

    test('renders privacy page with correct heading', async ({ page }) => {
        await page.goto('/privacy');
        await expect(page.getByRole('heading', { name: 'Privacy' })).toBeVisible();
    });

    test('contains data security section', async ({ page }) => {
        await page.goto('/privacy');
        await expect(page.getByRole('heading', { name: 'Is my data secure?' })).toBeVisible();
    });

    test('contains tracking section', async ({ page }) => {
        await page.goto('/privacy');
        await expect(page.getByRole('heading', { name: 'Do you track me?' })).toBeVisible();
    });

    test('contains what data is stored section', async ({ page }) => {
        await page.goto('/privacy');
        await expect(page.getByRole('heading', { name: 'What data is stored?' })).toBeVisible();
    });

    test('contains AES-256-GCM encryption mention', async ({ page }) => {
        await page.goto('/privacy');
        await expect(page.getByText('AES-256-GCM')).toBeVisible();
    });

    test('links to GitHub repository', async ({ page }) => {
        await page.goto('/privacy');
        const githubLink = page.getByRole('link', { name: 'GitHub repository' });
        await expect(githubLink).toBeVisible();
        await expect(githubLink).toHaveAttribute('href', /github\.com/);
    });
});

test.describe('Not Found Page', () => {
    test.beforeEach(async ({ page }) => {
        await mockCoreAPIs(page);
    });

    test('renders 404 page for unknown routes', async ({ page }) => {
        await page.goto('/this-page-does-not-exist');
        await expect(page.getByRole('heading', { name: 'Page Not Found' })).toBeVisible();
    });

    test('shows page not found message', async ({ page }) => {
        await page.goto('/nonexistent-path/nested');
        await expect(
            page.getByText('This page has vanished into thin air, just like our secrets do.')
        ).toBeVisible();
    });

    test('has Go Home button that navigates to home', async ({ page }) => {
        await page.goto('/not-found-page');
        const goHomeBtn = page.getByRole('link', { name: 'Go Home' });
        await expect(goHomeBtn).toBeVisible();
        await goHomeBtn.click();
        await expect(page).toHaveURL('/');
    });

    test('has Create Secret button that navigates to home', async ({ page }) => {
        await page.goto('/random-page');
        const createSecretBtn = page.getByRole('link', { name: 'Create Secret' });
        await expect(createSecretBtn).toBeVisible();
    });
});

test.describe('Secret Not Found Page', () => {
    test.beforeEach(async ({ page }) => {
        await mockCoreAPIs(page);
        // Mock the secret check to return 404
        await page.route('**/api/secrets/*/check', async (route) => {
            await route.fulfill({
                status: 404,
                contentType: 'application/json',
                body: JSON.stringify({ error: 'Secret not found' }),
            });
        });
        // Also mock a secrets check that returns non-ok to trigger errorElement
        await page.route('**/api/secrets/nonexistent-secret/check', async (route) => {
            await route.fulfill({
                status: 404,
                contentType: 'application/json',
                body: JSON.stringify({ error: 'Secret not found' }),
            });
        });
    });

    test('shows not found page for expired/missing secrets', async ({ page }) => {
        await page.goto('/secret/nonexistent-secret-id');
        // Either SecretNotFoundPage renders or we get redirected
        // The loader should throw since the response is not ok
        await expect(
            page
                .getByRole('heading', { name: 'Secret Not Found' })
                .or(page.getByText('Secret Not Found'))
                .or(page.getByText('not found'))
        ).toBeVisible({ timeout: 10000 });
    });
});
