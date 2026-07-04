import { expect, test } from '@playwright/test';
import { mockCoreAPIs } from './helpers/api-mocks';

/**
 * The RequestSecretPage lives at /request/:id and requires a ?token= query parameter.
 * Without the token, the component immediately shows an "invalid link" error (no API call).
 * With a valid token, it fetches GET /api/secret-requests/:id/info?token=...
 */

test.describe('Request Secret Page - Error States', () => {
    test.beforeEach(async ({ page }) => {
        await mockCoreAPIs(page);
    });

    test('shows invalid link error when no token is provided', async ({ page }) => {
        // Navigate without a ?token= query param — component shows error immediately
        await page.goto('/request/invalid-token-xyz');

        // Shows "Request Unavailable" heading — use exact match to avoid strict mode
        await expect(
            page.getByRole('heading', { name: 'Request Unavailable' })
        ).toBeVisible({ timeout: 10000 });
    });

    test('shows go to homepage link on error page', async ({ page }) => {
        // Navigate without token to trigger the error state with the Go to Homepage link
        await page.goto('/request/bad-token');

        await expect(
            page.getByRole('link', { name: /go to homepage/i })
        ).toBeVisible({ timeout: 10000 });
    });

    test('shows not-found error when info API returns 404', async ({ page }) => {
        // Mock the correct endpoint: GET /api/secret-requests/:id/info?token=...
        await page.route('**/api/secret-requests/**/info**', async (route) => {
            await route.fulfill({
                status: 404,
                contentType: 'application/json',
                body: JSON.stringify({ error: 'Not found' }),
            });
        });

        await page.goto('/request/missing-id?token=some-token');

        // Page shows "Request Unavailable" heading — use heading role to avoid toast conflicts
        await expect(
            page.getByRole('heading', { name: 'Request Unavailable' })
        ).toBeVisible({ timeout: 10000 });
    });

    test('shows already-fulfilled error when info API returns 410', async ({ page }) => {
        await page.route('**/api/secret-requests/**/info**', async (route) => {
            await route.fulfill({
                status: 410,
                contentType: 'application/json',
                body: JSON.stringify({ error: 'Already fulfilled' }),
            });
        });

        await page.goto('/request/fulfilled-id?token=some-token');

        // Page shows "Request Unavailable" heading — use heading role to avoid toast conflicts
        await expect(
            page.getByRole('heading', { name: 'Request Unavailable' })
        ).toBeVisible({ timeout: 10000 });
    });
});

test.describe('Request Secret Page - Valid Request Form', () => {
    test.beforeEach(async ({ page }) => {
        await mockCoreAPIs(page);

        // Mock the info endpoint to return a valid open request
        await page.route('**/api/secret-requests/**/info**', async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    id: 'valid-request-id',
                    title: 'AWS Credentials Request',
                    description: 'Please provide your AWS access keys',
                }),
            });
        });
    });

    test('renders the submit-a-secret form heading', async ({ page }) => {
        await page.goto('/request/valid-id?token=valid-token-123');

        await expect(
            page.getByRole('heading', { name: /submit a secret/i })
        ).toBeVisible({ timeout: 10000 });
    });

    test('shows the request title from the API response', async ({ page }) => {
        await page.goto('/request/valid-id?token=valid-token-123');

        await expect(page.getByText('AWS Credentials Request')).toBeVisible({ timeout: 10000 });
    });

    test('shows the editor for composing the secret', async ({ page }) => {
        await page.goto('/request/valid-id?token=valid-token-123');

        await expect(
            page.locator('.tiptap, [contenteditable="true"]').first()
        ).toBeVisible({ timeout: 10000 });
    });

    test('shows the submit secret button', async ({ page }) => {
        await page.goto('/request/valid-id?token=valid-token-123');

        await expect(
            page.getByRole('button', { name: /submit secret/i })
        ).toBeVisible({ timeout: 10000 });
    });

    test('submit button is disabled when editor is empty', async ({ page }) => {
        await page.goto('/request/valid-id?token=valid-token-123');

        const submitBtn = page.getByRole('button', { name: /submit secret/i });
        await expect(submitBtn).toBeVisible({ timeout: 10000 });
        await expect(submitBtn).toBeDisabled();
    });

    test('submit button becomes enabled after typing in editor', async ({ page }) => {
        await page.goto('/request/valid-id?token=valid-token-123');

        const editor = page.locator('.tiptap, [contenteditable="true"]').first();
        await expect(editor).toBeVisible({ timeout: 10000 });
        await editor.click();
        await editor.type('my-secret-value');

        const submitBtn = page.getByRole('button', { name: /submit secret/i });
        await expect(submitBtn).toBeEnabled({ timeout: 5000 });
    });
});
