/**
 * E2E tests for the main application layout and core navigation.
 * - Note tree
 * - Launcher bar
 * - Tab bar
 * - Right pane (sidebar)
 */
import { test, expect } from "@playwright/test";
import { login, openSettings, getNoteSplit } from "./helpers";

test.describe("Main app layout", () => {
    test.beforeEach(async ({ page }) => {
        await login(page);
    });

    test("main app loads with all key UI areas visible", async ({ page }) => {
        // Note tree
        await expect(page.locator(".tree-wrapper")).toBeVisible();
        // Launcher bar
        await expect(page.locator("#launcher-container")).toBeVisible();
        // Tab bar
        await expect(page.locator(".tab-row-widget-container")).toBeVisible();
        // Note split (editor area)
        await expect(getNoteSplit(page)).toBeVisible();
    });

    test("note tree shows root and Hidden Notes entries", async ({ page }) => {
        const tree = page.locator(".tree-wrapper");
        await expect(tree).toContainText("root");
        await expect(tree).toContainText("Hidden Notes");
    });

    test("clicking a note in the tree loads it in the editor", async ({ page }) => {
        const rootNote = page.locator(".tree-wrapper .fancytree-node").first();
        await rootNote.click();
        await page.waitForTimeout(500);

        // URL should update with a note ID hash
        expect(page.url()).toMatch(/#/);
        // Note split should be visible with content area
        await expect(getNoteSplit(page)).toBeVisible();
    });

    test("app page title is 'Trilium Notes'", async ({ page }) => {
        await expect(page).toHaveTitle(/Trilium/i);
    });

    test("right pane shows Table of Contents section", async ({ page }) => {
        const rightPane = page.locator("#right-pane");
        await expect(rightPane).toBeVisible();
        // The right pane shows "Table of Contents" and "highlights" sections
        await expect(rightPane).toContainText("Table of Contents");
    });

    test("right pane shows highlights section", async ({ page }) => {
        const rightPane = page.locator("#right-pane");
        // highlights section shows as "0 highlights" or similar
        const text = await rightPane.innerText();
        expect(text.toLowerCase()).toMatch(/highlight/i);
    });
});

test.describe("Launcher bar", () => {
    test.beforeEach(async ({ page }) => {
        await login(page);
    });

    test("launcher bar renders expected action buttons", async ({ page }) => {
        const launcher = page.locator("#launcher-container");
        // Should have several buttons
        const buttons = launcher.locator(".launcher-button");
        const count = await buttons.count();
        expect(count).toBeGreaterThanOrEqual(5);
    });

    test("create note into inbox button exists", async ({ page }) => {
        const btn = page.locator(".launcher-button[data-trigger-command='createNoteIntoInbox']");
        await expect(btn).toBeVisible();
    });

    test("search notes button exists", async ({ page }) => {
        const btn = page.locator(".launcher-button[data-trigger-command='searchNotes']");
        await expect(btn).toBeVisible();
    });

    test("jump to note button exists", async ({ page }) => {
        const btn = page.locator(".launcher-button[data-trigger-command='jumpToNote']");
        await expect(btn).toBeVisible();
    });

    test("recent changes button exists", async ({ page }) => {
        const btn = page.locator(".launcher-button[data-trigger-command='showRecentChanges']");
        await expect(btn).toBeVisible();
    });

    test("settings / cog button opens options dialog", async ({ page }) => {
        await openSettings(page);
        await expect(page.locator(".modal.options-dialog")).toBeVisible();
    });

    test("protected session button exists", async ({ page }) => {
        const btn = page.locator(".launcher-button[data-trigger-command='enterProtectedSession']");
        await expect(btn).toBeVisible();
    });
});

test.describe("Tab management", () => {
    test.beforeEach(async ({ page }) => {
        await login(page);
    });

    test("tab bar shows at least one tab", async ({ page }) => {
        const tabBar = page.locator(".tab-row-widget-container");
        const tabs = tabBar.locator(".note-tab-wrapper");
        const count = await tabs.count();
        expect(count).toBeGreaterThanOrEqual(1);
    });

    test("add new tab button creates a new tab", async ({ page }) => {
        const tabBar = page.locator(".tab-row-widget-container");
        const tabs = tabBar.locator(".note-tab-wrapper");
        const before = await tabs.count();

        const addTabBtn = page.locator('[data-trigger-command="openNewTab"]');
        await addTabBtn.click();
        await page.waitForTimeout(1000);

        const after = await tabs.count();
        expect(after).toBeGreaterThan(before);
    });
});
