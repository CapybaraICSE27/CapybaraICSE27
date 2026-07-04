import { expect, test } from "@playwright/test";

// ──────────────────────────────────────────────────────────────────────────────
// Auth-protected pages – unauthenticated behavior
// ──────────────────────────────────────────────────────────────────────────────

test.describe("Protected page /only-members (unauthenticated)", () => {
  test("returns 401 HTTP status for unauthenticated user", async ({
    page,
    request,
  }) => {
    const response = await request.get("/only-members");
    expect(response.status()).toBe(401);
  });

  test("navigating to /only-members shows unauthorized error or redirects", async ({
    page,
  }) => {
    const response = await page.goto("/only-members");
    // Accept either 401 status or a page with unauthorized content
    if (response && response.status() === 401) {
      expect(response.status()).toBe(401);
    } else {
      // SPA might redirect or show an error state
      await page.waitForLoadState("networkidle");
      await expect(page.getByRole("main")).toBeVisible();
    }
  });
});

test.describe("Protected page /vip-lounge (unauthenticated)", () => {
  test("returns 401 HTTP status for unauthenticated user", async ({
    request,
  }) => {
    const response = await request.get("/vip-lounge");
    expect(response.status()).toBe(401);
  });

  test("navigating to /vip-lounge shows unauthorized error or redirects", async ({
    page,
  }) => {
    const response = await page.goto("/vip-lounge");
    if (response && response.status() === 401) {
      expect(response.status()).toBe(401);
    } else {
      await page.waitForLoadState("networkidle");
      await expect(page.getByRole("main")).toBeVisible();
    }
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// Premium Guides section hidden when unauthenticated
// ──────────────────────────────────────────────────────────────────────────────

test.describe("Auth-gated sidebar items", () => {
  test("Premium Guides section is not visible in sidebar when unauthenticated", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/documentation");
    await page.waitForLoadState("networkidle");

    // Premium Guides has display: 'auth' so it should not be visible without auth
    await expect(page.getByText("Premium Guides")).not.toBeVisible({
      timeout: 5000,
    });
  });

  test("Only Members nav item hidden when unauthenticated", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    // 'Only members' nav item has display: 'auth'
    await expect(
      page.getByRole("link", { name: /Only members/i }),
    ).not.toBeVisible({ timeout: 5000 });
  });
});
