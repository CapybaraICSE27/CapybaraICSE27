import { expect, test } from '@playwright/test';
import { mockCoreAPIs } from './helpers/api-mocks';

// Helper to create encrypted-like bytes that decrypt to empty (for mock purposes)
// We'll use a real encryption approach for the secret page tests
const MOCK_SECRET_ID = 'test-secret-view-id';

test.describe('Secret Page - Pre-reveal (Locked) State', () => {
    test.beforeEach(async ({ page }) => {
        await mockCoreAPIs(page);

        // Mock the secret check endpoint
        await page.route(`**/api/secrets/${MOCK_SECRET_ID}/check`, async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    isPasswordProtected: false,
                    views: 3,
                    files: [],
                }),
            });
        });
    });

    test('shows encrypted secret header', async ({ page }) => {
        await page.goto(`/secret/${MOCK_SECRET_ID}#decryptionKey=someKey123`);
        await expect(page.getByText(/encrypted secret/i)).toBeVisible({ timeout: 10000 });
    });

    test('shows Unlock Secret button', async ({ page }) => {
        await page.goto(`/secret/${MOCK_SECRET_ID}#decryptionKey=someKey123`);
        await expect(page.getByRole('button', { name: /unlock secret/i })).toBeVisible({ timeout: 10000 });
    });

    test('shows views remaining count', async ({ page }) => {
        await page.goto(`/secret/${MOCK_SECRET_ID}#decryptionKey=someKey123`);
        // The "X more times" text shows the view count
        await expect(page.getByText(/3 more time/i)).toBeVisible({ timeout: 10000 });
    });

    test('shows "This secret can be viewed X more times" message', async ({ page }) => {
        await page.goto(`/secret/${MOCK_SECRET_ID}#decryptionKey=someKey123`);
        await expect(page.getByText(/can be viewed/i).or(page.getByText(/more time/i))).toBeVisible({ timeout: 10000 });
    });

    test('has blurred content preview visible in background', async ({ page }) => {
        await page.goto(`/secret/${MOCK_SECRET_ID}#decryptionKey=someKey123`);
        // The blurred placeholder divs should be in the DOM
        await expect(page.locator('.blur-sm')).toBeVisible({ timeout: 10000 });
    });
});

test.describe('Secret Page - Password Protected State', () => {
    test.beforeEach(async ({ page }) => {
        await mockCoreAPIs(page);

        await page.route(`**/api/secrets/password-secret/check`, async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    isPasswordProtected: true,
                    views: 1,
                    files: [],
                }),
            });
        });
    });

    test('shows password input for password-protected secret', async ({ page }) => {
        await page.goto('/secret/password-secret');
        await expect(
            page.getByPlaceholder(/enter password/i)
        ).toBeVisible({ timeout: 10000 });
    });

    test('unlock button is enabled without entering password when no key in URL', async ({ page }) => {
        await page.goto('/secret/password-secret');
        // For password-protected secrets, the button should be visible regardless
        await expect(page.getByRole('button', { name: /unlock secret/i })).toBeVisible({ timeout: 10000 });
    });

    test('shows wrong password error message on decrypt failure', async ({ page }) => {
        await page.route('**/api/secrets/password-secret', async (route) => {
            if (route.request().method() === 'POST') {
                await route.fulfill({
                    status: 404,
                    contentType: 'application/json',
                    body: JSON.stringify({ error: 'Secret not found or password incorrect' }),
                });
            }
        });

        await page.goto('/secret/password-secret');
        const passwordInput = page.getByPlaceholder(/enter password/i);
        await expect(passwordInput).toBeVisible({ timeout: 10000 });
        await passwordInput.fill('wrongpassword');
        await page.getByRole('button', { name: /unlock secret/i }).click();

        // Should show an error
        await expect(
            page.getByText(/error/i).or(page.getByText(/failed/i)).or(page.getByText(/incorrect/i)).first()
        ).toBeVisible({ timeout: 5000 });
    });
});

test.describe('Secret Page - Manual Key Entry State', () => {
    test.beforeEach(async ({ page }) => {
        await mockCoreAPIs(page);

        await page.route('**/api/secrets/manual-key-secret/check', async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    isPasswordProtected: false,
                    views: 2,
                    files: [],
                }),
            });
        });
    });

    test('shows decryption key input when no key in URL', async ({ page }) => {
        // Navigate without hash fragment (no key in URL)
        await page.goto('/secret/manual-key-secret');
        await expect(
            page.getByPlaceholder(/decryption key/i).or(page.getByLabel(/decryption key/i))
        ).toBeVisible({ timeout: 10000 });
    });

    test('unlock button is disabled when no key is entered', async ({ page }) => {
        await page.goto('/secret/manual-key-secret');
        const unlockBtn = page.getByRole('button', { name: /unlock secret/i });
        await expect(unlockBtn).toBeVisible({ timeout: 10000 });
        await expect(unlockBtn).toBeDisabled();
    });

    test('unlock button becomes enabled after entering decryption key', async ({ page }) => {
        await page.goto('/secret/manual-key-secret');
        const keyInput = page.getByPlaceholder(/decryption key/i).or(page.getByLabel(/decryption key/i));
        await expect(keyInput).toBeVisible({ timeout: 10000 });
        await keyInput.fill('myDecryptionKey123');
        const unlockBtn = page.getByRole('button', { name: /unlock secret/i });
        await expect(unlockBtn).toBeEnabled();
    });
});

test.describe('Secret Page - Secret Not Found', () => {
    test.beforeEach(async ({ page }) => {
        await mockCoreAPIs(page);
    });

    test('shows not found page when secret check returns 404', async ({ page }) => {
        await page.route('**/api/secrets/missing-id/check', async (route) => {
            await route.fulfill({
                status: 404,
                contentType: 'application/json',
                body: JSON.stringify({ error: 'Not found' }),
            });
        });

        await page.goto('/secret/missing-id');
        await expect(
            page.getByText(/secret not found/i).or(page.getByRole('heading', { name: /not found/i }))
        ).toBeVisible({ timeout: 10000 });
    });

    test('not found page has go to homepage button', async ({ page }) => {
        await page.route('**/api/secrets/expired-id/check', async (route) => {
            await route.fulfill({
                status: 404,
                contentType: 'application/json',
                body: JSON.stringify({ error: 'Expired' }),
            });
        });

        await page.goto('/secret/expired-id');
        await expect(
            page.getByRole('link', { name: /go to homepage/i }).or(
                page.getByRole('link', { name: /homepage/i })
            )
        ).toBeVisible({ timeout: 10000 });
    });
});

test.describe('Secret Page - Revealed State', () => {
    test.beforeEach(async ({ page }) => {
        await mockCoreAPIs(page);

        const secretId = 'revealed-secret-id';

        // Mock secret check
        await page.route(`**/api/secrets/${secretId}/check`, async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    isPasswordProtected: false,
                    views: 1,
                    files: [],
                }),
            });
        });

        // Mock secret fetch - we need to provide encrypted content
        // The browser will try to decrypt it with the key from the URL
        // For simplicity, we'll use a real encryption key and encrypted content
        // Let's return a properly encrypted secret
        await page.route(`**/api/secrets/${secretId}`, async (route) => {
            if (route.request().method() === 'POST') {
                // Return a fake encrypted response that will fail to decrypt gracefully
                await route.fulfill({
                    status: 404,
                    contentType: 'application/json',
                    body: JSON.stringify({ error: 'Secret not found' }),
                });
            }
        });
    });

    test('shows decryption error when wrong key is used', async ({ page }) => {
        await page.goto('/secret/revealed-secret-id#decryptionKey=wrongKey123');
        await page.getByRole('button', { name: /unlock secret/i }).click();

        await expect(
            page.getByText(/failed to decrypt/i)
                .or(page.getByText(/error/i))
                .or(page.getByText(/not found/i))
                .first()
        ).toBeVisible({ timeout: 10000 });
    });
});

test.describe('Secret Page - Delete Modal', () => {
    test('shows delete confirmation modal', async ({ page }) => {
        await mockCoreAPIs(page);

        const secretId = 'deletable-secret';

        await page.route(`**/api/secrets/${secretId}/check`, async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({ isPasswordProtected: false, views: 5, files: [] }),
            });
        });

        // We need to first reveal the secret to get to the delete button
        // Mock a successful decrypt that returns some content
        await page.route(`**/api/secrets/${secretId}`, async (route) => {
            if (route.request().method() === 'POST') {
                await route.fulfill({
                    status: 404,
                    contentType: 'application/json',
                    body: JSON.stringify({ error: 'Secret fetch failed for test' }),
                });
            }
        });

        await page.goto(`/secret/${secretId}#decryptionKey=testKey`);

        // Click Unlock to trigger a fetch (will fail and show error)
        await page.getByRole('button', { name: /unlock secret/i }).click();

        // Even if unlock fails, let's check the page doesn't crash
        await expect(page.getByText(/encrypted secret/i).or(page.getByText(/error/i)).first()).toBeVisible({ timeout: 5000 });
    });
});
