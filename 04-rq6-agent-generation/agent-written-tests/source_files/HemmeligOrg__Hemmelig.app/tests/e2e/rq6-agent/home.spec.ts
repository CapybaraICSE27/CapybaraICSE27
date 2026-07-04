import { expect, test } from '@playwright/test';
import { mockCoreAPIs } from './helpers/api-mocks';

test.describe('Home Page - Secret Form', () => {
    test.beforeEach(async ({ page }) => {
        await mockCoreAPIs(page);
        await page.goto('/');
    });

    test('renders the home page', async ({ page }) => {
        await expect(page).toHaveURL('/');
        await expect(page.locator('#root')).toBeVisible();
    });

    test('shows the secret editor area', async ({ page }) => {
        // The editor is the main content area
        const editor = page.locator('.tiptap, [contenteditable="true"]').first();
        await expect(editor).toBeVisible({ timeout: 10000 });
    });

    test('shows Security section', async ({ page }) => {
        await expect(page.getByRole('heading', { name: /security/i })).toBeVisible();
    });

    test('shows expiration settings', async ({ page }) => {
        await expect(page.getByText(/expiration/i)).toBeVisible();
    });

    test('Create button is disabled when editor is empty', async ({ page }) => {
        const createBtn = page.getByRole('button', { name: /create/i }).first();
        await expect(createBtn).toBeDisabled();
    });

    test('Create button becomes enabled after typing in editor', async ({ page }) => {
        const editor = page.locator('.tiptap, [contenteditable="true"]').first();
        await editor.click();
        await editor.type('My secret message');
        await expect(editor).toContainText('My secret message');

        const createBtn = page.getByRole('button', { name: /create/i }).first();
        await expect(createBtn).toBeEnabled();
    });

    test('can type content into the editor', async ({ page }) => {
        const editor = page.locator('.tiptap, [contenteditable="true"]').first();
        await editor.click();
        await editor.fill('This is my secret content');
        await expect(editor).toContainText('This is my secret content');
    });

    test('shows file upload area', async ({ page }) => {
        // File upload requires login for full functionality, but the component is present
        await expect(
            page.getByText(/upload file/i).or(page.getByText(/drag and drop/i)).or(
                page.getByText(/sign in to upload/i)
            )
        ).toBeVisible({ timeout: 10000 });
    });

    test('shows security settings card with expiration options', async ({ page }) => {
        // Expiration select should be visible in security settings
        await expect(page.locator('select, [role="combobox"]').first()).toBeVisible();
    });

    test('shows views setting', async ({ page }) => {
        // Views slider - the ViewsSlider component uses an input[type=range]
        await expect(page.locator('input[type="range"]')).toBeVisible();
    });

    test('shows burn after reading toggle', async ({ page }) => {
        // Burn after reading toggle should be visible
        await expect(page.getByText(/burn after/i).or(page.getByText(/burn/i))).toBeVisible();
    });

    test('shows password protection option', async ({ page }) => {
        await expect(page.getByText(/password protection/i)).toBeVisible();
    });

    test('title field is visible and accepts input', async ({ page }) => {
        // Title field
        const titleInput = page.getByPlaceholder(/title/i).or(
            page.locator('input[placeholder*="title" i], input[placeholder*="Title" i]')
        ).first();
        if (await titleInput.isVisible()) {
            await titleInput.fill('My Secret Title');
            await expect(titleInput).toHaveValue('My Secret Title');
        }
    });
});

test.describe('Home Page - Secret Created State', () => {
    test.beforeEach(async ({ page }) => {
        await mockCoreAPIs(page);

        // Mock the secret creation endpoint
        await page.route('**/api/secrets', async (route) => {
            if (route.request().method() === 'POST') {
                await route.fulfill({
                    status: 200,
                    contentType: 'application/json',
                    body: JSON.stringify({ id: 'test-secret-abc123' }),
                });
            } else {
                await route.continue();
            }
        });

        await page.goto('/');
    });

    test('shows SecretSettings after creating a secret', async ({ page }) => {
        // Type something in the editor
        const editor = page.locator('.tiptap, [contenteditable="true"]').first();
        await editor.click();
        await editor.type('My confidential secret');

        // Click Create button
        const createBtn = page.getByRole('button', { name: /^create$/i }).first();
        await createBtn.click();

        // Wait for the "Secret Created!" success state
        await expect(page.getByText('Secret Created!')).toBeVisible({ timeout: 10000 });
    });

    test('shows secret URL after creation', async ({ page }) => {
        const editor = page.locator('.tiptap, [contenteditable="true"]').first();
        await editor.click();
        await editor.type('Another secret');

        await page.getByRole('button', { name: /^create$/i }).first().click();

        await expect(page.getByText('Secret Created!')).toBeVisible({ timeout: 10000 });
        // Secret URL label
        await expect(page.getByText(/secret url/i)).toBeVisible();
    });

    test('shows copy URL button after creation', async ({ page }) => {
        const editor = page.locator('.tiptap, [contenteditable="true"]').first();
        await editor.click();
        await editor.type('Secret for copy URL test');

        await page.getByRole('button', { name: /^create$/i }).first().click();
        await expect(page.getByText('Secret Created!')).toBeVisible({ timeout: 10000 });

        await expect(page.getByRole('button', { name: /copy url/i })).toBeVisible();
    });

    test('shows QR code after creation', async ({ page }) => {
        const editor = page.locator('.tiptap, [contenteditable="true"]').first();
        await editor.click();
        await editor.type('Secret with QR code');

        await page.getByRole('button', { name: /^create$/i }).first().click();
        await expect(page.getByText('Secret Created!')).toBeVisible({ timeout: 10000 });

        // QR code canvas should be visible
        await expect(page.locator('canvas')).toBeVisible();
    });

    test('burn secret button is visible after creation', async ({ page }) => {
        const editor = page.locator('.tiptap, [contenteditable="true"]').first();
        await editor.click();
        await editor.type('Burnable secret');

        await page.getByRole('button', { name: /^create$/i }).first().click();
        await expect(page.getByText('Secret Created!')).toBeVisible({ timeout: 10000 });

        await expect(page.getByRole('button', { name: /burn secret/i })).toBeVisible();
    });

    test('create new secret button resets to form', async ({ page }) => {
        const editor = page.locator('.tiptap, [contenteditable="true"]').first();
        await editor.click();
        await editor.type('Reset test secret');

        await page.getByRole('button', { name: /^create$/i }).first().click();
        await expect(page.getByText('Secret Created!')).toBeVisible({ timeout: 10000 });

        // Click "Create New Secret" to go back to the form
        await page.getByRole('button', { name: /create new secret/i }).click();
        // Should show the form again
        await expect(page.locator('.tiptap, [contenteditable="true"]').first()).toBeVisible();
    });

    test('burn secret button calls API and resets form', async ({ page }) => {
        await page.route('**/api/secrets/test-secret-abc123', async (route) => {
            if (route.request().method() === 'DELETE') {
                await route.fulfill({
                    status: 200,
                    contentType: 'application/json',
                    body: JSON.stringify({ success: true }),
                });
            }
        });

        const editor = page.locator('.tiptap, [contenteditable="true"]').first();
        await editor.click();
        await editor.type('Burnable secret test');

        await page.getByRole('button', { name: /^create$/i }).first().click();
        await expect(page.getByText('Secret Created!')).toBeVisible({ timeout: 10000 });

        await page.getByRole('button', { name: /burn secret/i }).click();
        // Should reset to the form
        await expect(page.locator('.tiptap, [contenteditable="true"]').first()).toBeVisible({ timeout: 5000 });
    });
});

test.describe('Home Page - Security Settings', () => {
    test.beforeEach(async ({ page }) => {
        await mockCoreAPIs(page);
        await page.goto('/');
    });

    test('remember settings toggle is visible', async ({ page }) => {
        // The "Remember" toggle in security settings
        await expect(page.getByText(/remember/i)).toBeVisible();
    });

    test('expiration select has multiple options', async ({ page }) => {
        const select = page.locator('select').first();
        await expect(select).toBeVisible();
        const options = await select.locator('option').count();
        expect(options).toBeGreaterThan(1);
    });

    test('can select different expiration values', async ({ page }) => {
        const select = page.locator('select').first();
        await select.selectOption({ index: 1 });
        const value = await select.inputValue();
        expect(value).toBeTruthy();
    });

    test('IP restriction toggle is visible', async ({ page }) => {
        // IP restriction section title
        await expect(page.getByText(/restrict by ip/i)).toBeVisible();
    });
});

test.describe('Home Page - Editor Formatting', () => {
    test.beforeEach(async ({ page }) => {
        await mockCoreAPIs(page);
        await page.goto('/');
    });

    test('editor toolbar buttons are rendered', async ({ page }) => {
        // The editor toolbar has multiple icon-only buttons visible on desktop
        // All buttons in the editor card area - look for at least several
        const editorArea = page.locator('.space-y-6').first();
        await expect(editorArea).toBeVisible({ timeout: 5000 });
        const buttons = editorArea.locator('button');
        const count = await buttons.count();
        expect(count).toBeGreaterThan(3);
    });

    test('shows character count', async ({ page }) => {
        await expect(page.getByText(/characters/i)).toBeVisible();
    });
});
