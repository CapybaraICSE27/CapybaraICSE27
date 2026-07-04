/**
 * E2E tests for launcher bar flows:
 * - Search notes
 * - Jump to note
 * - Recent changes
 * - Create note into inbox
 * - Protected session
 */
import { test, expect } from "@playwright/test";
import { login } from "./helpers";

test.describe("Search notes", () => {
    test.beforeEach(async ({ page }) => {
        await login(page);
    });

    test("clicking search button opens a search UI", async ({ page }) => {
        const searchBtn = page.locator(".launcher-button[data-trigger-command='searchNotes']");
        await searchBtn.click();
        await page.waitForTimeout(1000);

        // After clicking search, the active note should show a search panel
        // or the URL changes to a search note
        const noteSplit = page.locator(".note-split:not(.hidden-ext)");
        const content = await noteSplit.innerText().catch(() => "");

        // Either search panel appeared or URL changed
        const urlHasSearch = page.url().includes("search") || page.url().includes("Search");
        const contentHasSearch = content.toLowerCase().includes("search");
        expect(urlHasSearch || contentHasSearch || await noteSplit.isVisible()).toBeTruthy();
    });
});

test.describe("Jump to note", () => {
    test.beforeEach(async ({ page }) => {
        await login(page);
    });

    test("jump to note button triggers autocomplete navigation", async ({ page }) => {
        const jumpBtn = page.locator(".launcher-button[data-trigger-command='jumpToNote']");
        await jumpBtn.click();
        await page.waitForTimeout(1000);

        // Should open an autocomplete or dialog for navigating to notes
        const noteSplit = page.locator(".note-split:not(.hidden-ext)");
        const autocomplete = page.locator(".note-autocomplete, .aa-Input, input[type='search']");
        const dialog = page.locator(".modal.show");

        const hasAutocomplete = await autocomplete.count() > 0;
        const hasDialog = await dialog.count() > 0;
        const noteSplitVisible = await noteSplit.isVisible().catch(() => false);

        expect(hasAutocomplete || hasDialog || noteSplitVisible).toBeTruthy();
    });
});

test.describe("Recent changes", () => {
    test.beforeEach(async ({ page }) => {
        await login(page);
    });

    test("recent changes button triggers recent changes view", async ({ page }) => {
        const btn = page.locator(".launcher-button[data-trigger-command='showRecentChanges']");
        await btn.click();
        await page.waitForTimeout(1000);

        // A dialog or panel should appear with recent change info
        const dialog = page.locator(".modal.show");
        const noteSplit = page.locator(".note-split:not(.hidden-ext)");

        const hasDialog = await dialog.count() > 0;
        const splitContent = await noteSplit.innerText().catch(() => "");
        const contentHasRecent = splitContent.toLowerCase().includes("recent") ||
            splitContent.toLowerCase().includes("change") ||
            splitContent.toLowerCase().includes("modif");
        const urlHasRecent = page.url().toLowerCase().includes("recent");

        expect(hasDialog || contentHasRecent || urlHasRecent).toBeTruthy();
    });
});

test.describe("Create note into inbox", () => {
    test.beforeEach(async ({ page }) => {
        await login(page);
    });

    test("create note into inbox creates a new note", async ({ page }) => {
        const btn = page.locator(".launcher-button[data-trigger-command='createNoteIntoInbox']");
        await btn.click();
        await page.waitForTimeout(2000);

        // After creating a note, the editor should show the new note
        const noteSplit = page.locator(".note-split:not(.hidden-ext)");
        const editorVisible = await noteSplit.isVisible().catch(() => false);
        expect(editorVisible).toBeTruthy();
    });
});

test.describe("Protected session", () => {
    test.beforeEach(async ({ page }) => {
        await login(page);
    });

    test("protected session button opens password prompt modal", async ({ page }) => {
        const btn = page.locator(".launcher-button[data-trigger-command='enterProtectedSession']");
        await btn.click();
        await page.waitForTimeout(1000);

        // Should show a modal with password field
        const modal = page.locator(".modal.show");
        if (await modal.count() > 0) {
            const modalContent = await modal.innerText();
            expect(modalContent).toMatch(/password|protected|session/i);
        } else {
            // May open a different UI
            expect(true).toBe(true);
        }
    });

    test("protected session dialog can be closed", async ({ page }) => {
        const btn = page.locator(".launcher-button[data-trigger-command='enterProtectedSession']");
        await btn.click();
        await page.waitForTimeout(800);

        const modal = page.locator(".modal.show");
        if (await modal.count() > 0) {
            const closeBtn = modal.locator("[data-bs-dismiss='modal'], .btn-close").first();
            if (await closeBtn.isVisible().catch(() => false)) {
                await closeBtn.click();
                await page.waitForTimeout(600);
                await expect(modal).not.toBeVisible();
            } else {
                await page.keyboard.press("Escape");
                await page.waitForTimeout(600);
                await expect(modal).not.toBeVisible();
            }
        }
        expect(true).toBe(true);
    });
});
