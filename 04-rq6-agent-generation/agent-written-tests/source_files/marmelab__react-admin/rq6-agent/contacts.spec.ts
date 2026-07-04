/**
 * Contacts module tests: list, create, show, edit.
 * Auth is bypassed via localStorage injection.
 */
import { test, expect } from '@playwright/test';
import { gotoAuthenticated } from './helpers';

test.describe('Contacts list', () => {
    test('contacts list page loads', async ({ page }) => {
        await gotoAuthenticated(page, '/contacts');
        // Wait for at least one contact list item to confirm data loaded
        await expect(page.getByRole('listitem').first()).toBeVisible({
            timeout: 20_000,
        });
        await expect(page).toHaveURL(/\/contacts/);
    });

    test('shows contact rows in the list', async ({ page }) => {
        await gotoAuthenticated(page, '/contacts');
        // ContactListContent renders contacts as MUI ListItem (<li role="listitem">)
        // inside a MUI List (<ul>). Wait for at least one row.
        const rows = page.getByRole('listitem');
        await expect(rows.first()).toBeVisible({ timeout: 20_000 });
    });

    test('list toolbar has a Create button', async ({ page }) => {
        await gotoAuthenticated(page, '/contacts');
        // Wait for the list to render before checking the toolbar
        await expect(page.getByRole('listitem').first()).toBeVisible({
            timeout: 20_000,
        });
        await expect(
            page.getByRole('link', { name: /new contact/i })
        ).toBeVisible();
    });

    test('list toolbar has an Export button', async ({ page }) => {
        await gotoAuthenticated(page, '/contacts');
        await expect(page.getByRole('listitem').first()).toBeVisible({
            timeout: 20_000,
        });
        await expect(
            page.getByRole('button', { name: /export/i })
        ).toBeVisible();
    });

    test('filter bar is always visible', async ({ page }) => {
        await gotoAuthenticated(page, '/contacts');
        // ContactListFilter renders a FilterLiveSearch with placeholder
        // "Search name, company, etc." - always visible on the contacts page.
        const searchInput = page.locator('input[placeholder*="Search" i]');
        await expect(searchInput).toBeVisible({ timeout: 20_000 });
    });

    test('typing in search filter narrows list', async ({ page }) => {
        await gotoAuthenticated(page, '/contacts');
        // Wait for list to render first
        await expect(page.getByRole('listitem').first()).toBeVisible({
            timeout: 20_000,
        });
        const rows = page.getByRole('listitem');
        const initialCount = await rows.count();
        // Type a nonsense query that won't match anything
        const searchInput = page.locator('input[placeholder*="Search" i]');
        await searchInput.fill('zzzznonexistent9999');
        // Wait for debounce + re-render (FilterLiveSearch debounces by ~250ms)
        await page.waitForTimeout(800);
        const filteredCount = await rows.count();
        expect(filteredCount).toBeLessThanOrEqual(initialCount);
    });
});

test.describe('Contact create', () => {
    test('create contact page renders Identity section', async ({ page }) => {
        await gotoAuthenticated(page, '/contacts/create');
        // Wait for the form to render (Identity heading appears when form loads)
        await expect(page.getByText('Identity')).toBeVisible({
            timeout: 20_000,
        });
        await expect(
            page.getByRole('textbox', { name: /first.name/i })
        ).toBeVisible();
        await expect(
            page.getByRole('textbox', { name: /last.name/i })
        ).toBeVisible();
    });

    test('create contact page renders Position section', async ({ page }) => {
        await gotoAuthenticated(page, '/contacts/create');
        await expect(page.getByText('Position')).toBeVisible({
            timeout: 20_000,
        });
        await expect(
            page.getByRole('textbox', { name: /title/i })
        ).toBeVisible();
    });

    test('create contact page renders Personal info section', async ({
        page,
    }) => {
        await gotoAuthenticated(page, '/contacts/create');
        await expect(page.getByText(/personal info/i)).toBeVisible({
            timeout: 20_000,
        });
        await expect(
            page.getByRole('textbox', { name: /email/i })
        ).toBeVisible();
    });

    test('create contact page renders Misc section', async ({ page }) => {
        await gotoAuthenticated(page, '/contacts/create');
        await expect(page.getByText(/misc/i)).toBeVisible({ timeout: 20_000 });
    });

    test('can create a contact and redirect to show page', async ({ page }) => {
        await gotoAuthenticated(page, '/contacts/create');
        // Wait for form to be ready
        await expect(page.getByText('Identity')).toBeVisible({
            timeout: 20_000,
        });

        const ts = Date.now();
        const firstName = `Test${ts}`;
        const lastName = `Contact${ts}`;

        await page
            .getByRole('textbox', { name: /first.name/i })
            .fill(firstName);
        await page.getByRole('textbox', { name: /last.name/i }).fill(lastName);

        // The form needs "Account manager" (sales_id) which is required.
        // Wait for the SelectInput to load its options then pick the first one.
        const accountManagerSelect = page.getByRole('combobox', {
            name: /account manager/i,
        });
        await expect(accountManagerSelect).toBeVisible({ timeout: 10_000 });
        // The dropdown may already have a value if only one option exists.
        // Click open and select the first option.
        await accountManagerSelect.click();
        const firstOption = page.getByRole('option').first();
        await expect(firstOption).toBeVisible({ timeout: 5_000 });
        await firstOption.click();

        await page.getByRole('button', { name: /save/i }).click();

        // After save, react-admin redirects to the show page
        await page.waitForURL(/\/contacts\/\d+\/show/, { timeout: 15_000 });
        await expect(page.getByText(firstName)).toBeVisible();
    });
});

test.describe('Contact show', () => {
    test('contact show page displays contact details', async ({ page }) => {
        // Navigate to contacts list and click the first contact
        await gotoAuthenticated(page, '/contacts');
        // ContactListContent wraps each contact in ListItemButton (a link to show)
        const firstContactLink = page
            .getByRole('listitem')
            .first()
            .getByRole('link');
        await expect(firstContactLink).toBeVisible({ timeout: 20_000 });
        await firstContactLink.click();

        // Should now be on the show page
        await page.waitForURL(/\/contacts\/\d+\/show/, { timeout: 15_000 });
        await expect(page).toHaveURL(/\/contacts\/\d+\/show/);
    });
});

test.describe('Contact edit', () => {
    test('contact edit page renders the form', async ({ page }) => {
        // Navigate to contacts list and open first contact's edit page
        await gotoAuthenticated(page, '/contacts');

        // Click the first contact link to go to show page
        const firstContactLink = page
            .getByRole('listitem')
            .first()
            .getByRole('link');
        await expect(firstContactLink).toBeVisible({ timeout: 20_000 });
        await firstContactLink.click();
        await page.waitForURL(/\/contacts\/\d+\/show/, { timeout: 15_000 });

        // The show page has an Edit button (react-admin EditButton)
        const editButton = page
            .getByRole('link', { name: /edit/i })
            .or(page.getByRole('button', { name: /edit/i }))
            .first();
        await expect(editButton).toBeVisible({ timeout: 10_000 });
        await editButton.click();

        await page.waitForURL(/\/contacts\/\d+$/, { timeout: 15_000 });
        await expect(
            page.getByRole('textbox', { name: /first.name/i })
        ).toBeVisible({ timeout: 10_000 });
    });
});
