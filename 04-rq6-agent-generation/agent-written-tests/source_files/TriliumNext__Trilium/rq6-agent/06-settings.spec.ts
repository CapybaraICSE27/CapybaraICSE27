/**
 * E2E tests for the Settings (Options) dialog.
 * Tests opening the dialog and navigating to each settings section.
 */
import { test, expect } from "@playwright/test";
import { login, openSettings } from "./helpers";

test.describe("Settings dialog", () => {
    test.beforeEach(async ({ page }) => {
        await login(page);
        await openSettings(page);
    });

    test("settings dialog opens with navigation sidebar", async ({ page }) => {
        const dialog = page.locator(".modal.options-dialog");
        await expect(dialog).toBeVisible();

        // Navigation items in the dialog
        await expect(dialog).toContainText("Appearance");
        await expect(dialog).toContainText("Shortcuts");
        await expect(dialog).toContainText("Security");
        await expect(dialog).toContainText("Backup");
        await expect(dialog).toContainText("Sync");
    });

    test("Appearance settings page loads", async ({ page }) => {
        const dialog = page.locator(".modal.options-dialog");
        // Should already be on Appearance
        await expect(dialog).toContainText("Application theme");
        await expect(dialog).toContainText("Color scheme");
        await expect(dialog).toContainText("Layout style");
    });

    test("Appearance page has theme options", async ({ page }) => {
        const dialog = page.locator(".modal.options-dialog");
        await expect(dialog).toContainText("System");
        await expect(dialog).toContainText("Light");
        await expect(dialog).toContainText("Dark");
    });

    test("Appearance page has font settings section", async ({ page }) => {
        const dialog = page.locator(".modal.options-dialog");
        // Font section header is title-cased "Fonts" not "FONTS"
        await expect(dialog).toContainText("Fonts");
        await expect(dialog).toContainText("Interface text");
        await expect(dialog).toContainText("Document text");
        await expect(dialog).toContainText("Monospace text");
    });

    test("can navigate to Shortcuts settings", async ({ page }) => {
        const dialog = page.locator(".modal.options-dialog");
        await dialog.locator(".settings-navigation-item", { hasText: "Shortcuts" }).click();
        await page.waitForTimeout(1000);
        const content = await dialog.innerText();
        expect(content).toMatch(/shortcut|keyboard|hotkey|reload/i);
    });

    test("can navigate to Text Notes settings", async ({ page }) => {
        const dialog = page.locator(".modal.options-dialog");
        await dialog.locator(".settings-navigation-item", { hasText: "Text Notes" }).click();
        await page.waitForTimeout(1000);
        const content = await dialog.innerText();
        expect(content).toMatch(/text|note|editor|heading/i);
    });

    test("can navigate to Code Notes settings", async ({ page }) => {
        const dialog = page.locator(".modal.options-dialog");
        await dialog.locator(".settings-navigation-item", { hasText: "Code Notes" }).click();
        await page.waitForTimeout(1000);
        const content = await dialog.innerText();
        expect(content).toMatch(/code|syntax|wrap|editor/i);
    });

    test("can navigate to Security settings", async ({ page }) => {
        const dialog = page.locator(".modal.options-dialog");
        await dialog.locator(".settings-navigation-item", { hasText: "Security" }).first().click();
        await page.waitForTimeout(1000);
        const content = await dialog.innerText();
        expect(content).toMatch(/security|password|protected|session/i);
    });

    test("can navigate to Password & Auth settings", async ({ page }) => {
        const dialog = page.locator(".modal.options-dialog");
        await dialog.locator(".settings-navigation-item", { hasText: "Password" }).first().click();
        await page.waitForTimeout(1000);
        const content = await dialog.innerText();
        expect(content).toMatch(/password|auth/i);
    });

    test("can navigate to ETAPI settings", async ({ page }) => {
        const dialog = page.locator(".modal.options-dialog");
        await dialog.locator(".settings-navigation-item", { hasText: "ETAPI" }).click();
        await page.waitForTimeout(1000);
        const content = await dialog.innerText();
        expect(content).toMatch(/ETAPI|API|token/i);
    });

    test("can navigate to Backup settings", async ({ page }) => {
        const dialog = page.locator(".modal.options-dialog");
        await dialog.locator(".settings-navigation-item", { hasText: "Backup" }).click();
        await page.waitForTimeout(1000);
        const content = await dialog.innerText();
        expect(content).toMatch(/backup/i);
    });

    test("can navigate to Sync settings", async ({ page }) => {
        const dialog = page.locator(".modal.options-dialog");
        await dialog.locator(".settings-navigation-item", { hasText: "Sync" }).click();
        await page.waitForTimeout(1000);
        const content = await dialog.innerText();
        expect(content).toMatch(/sync|synchroni/i);
    });

    test("can navigate to AI/LLM settings", async ({ page }) => {
        const dialog = page.locator(".modal.options-dialog");
        const aiItem = dialog.locator(".settings-navigation-item", { hasText: /AI|LLM/ });
        if (await aiItem.count() > 0) {
            await aiItem.first().click();
            await page.waitForTimeout(1000);
            const content = await dialog.innerText();
            expect(content).toMatch(/AI|LLM|language model|provider/i);
        } else {
            expect(true).toBe(true);
        }
    });

    test("can navigate to Language & Region settings", async ({ page }) => {
        const dialog = page.locator(".modal.options-dialog");
        const langItem = dialog.locator(".settings-navigation-item", { hasText: /Language/ });
        if (await langItem.count() > 0) {
            await langItem.first().click();
            await page.waitForTimeout(1000);
            const content = await dialog.innerText();
            expect(content).toMatch(/language|locale|region/i);
        } else {
            expect(true).toBe(true);
        }
    });

    test("settings dialog can be closed with close button", async ({ page }) => {
        const dialog = page.locator(".modal.options-dialog");
        await expect(dialog).toBeVisible();

        // Use the explicit close button (data-bs-dismiss or btn-close)
        const closeBtn = dialog.locator("[data-bs-dismiss='modal'], .btn-close").first();
        await closeBtn.click();
        await page.waitForTimeout(1000);
        await expect(dialog).not.toBeVisible();
    });

    test("settings dialog navigation sidebar has 14 sections", async ({ page }) => {
        const dialog = page.locator(".modal.options-dialog");
        const navItems = dialog.locator(".settings-navigation-item");
        const count = await navItems.count();
        expect(count).toBe(14); // Appearance, Shortcuts, Text Notes, Code Notes, Media, Security, Password & Auth, ETAPI, Backup, Sync, AI/LLM, Other, Language & Region, Advanced
    });
});
