import { expect, test } from '@playwright/test';
import { MOCK_USER, mockCoreAPIs, mockDashboardAPIs } from './helpers/api-mocks';

test.describe('Dashboard - Authentication Guard', () => {
    test('redirects unauthenticated user from /dashboard to /login', async ({ page }) => {
        await mockCoreAPIs(page, { authenticated: false });
        await page.goto('/dashboard');
        await expect(page).toHaveURL('/login', { timeout: 10000 });
    });

    test('redirects unauthenticated user from /dashboard/account to /login', async ({ page }) => {
        await mockCoreAPIs(page, { authenticated: false });
        await page.goto('/dashboard/account');
        await expect(page).toHaveURL('/login', { timeout: 10000 });
    });

    test('redirects unauthenticated user from /dashboard/users to /login', async ({ page }) => {
        await mockCoreAPIs(page, { authenticated: false });
        await page.goto('/dashboard/users');
        await expect(page).toHaveURL('/login', { timeout: 10000 });
    });
});

test.describe('Dashboard - Authenticated Access', () => {
    test.beforeEach(async ({ page }) => {
        await mockCoreAPIs(page, { authenticated: true });
        await mockDashboardAPIs(page);
        // Navigate to root first to populate instance settings in the Zustand store
        await page.goto('/');
    });

    test('loads dashboard page when authenticated', async ({ page }) => {
        await page.goto('/dashboard');
        // Should not redirect to login
        await expect(page).toHaveURL('/dashboard', { timeout: 10000 });
    });

    test('shows dashboard navigation with Secrets link', async ({ page }) => {
        await page.goto('/dashboard');
        await expect(page.getByRole('link', { name: /secrets/i }).first()).toBeVisible({ timeout: 10000 });
    });

    test('shows dashboard navigation with Account link', async ({ page }) => {
        await page.goto('/dashboard');
        await expect(page.getByRole('link', { name: /account/i })).toBeVisible({ timeout: 10000 });
    });

    test('shows Hemmelig branding in dashboard header', async ({ page }) => {
        await page.goto('/dashboard');
        await expect(page.getByText(/hemmelig/i).first()).toBeVisible({ timeout: 10000 });
    });

    test('shows Sign Out button/link', async ({ page }) => {
        await page.goto('/dashboard');
        // The sign out button is in the desktop sidebar
        await expect(page.getByText('Sign out')).toBeVisible({ timeout: 10000 });
    });

    test('shows empty secrets list message or secrets title', async ({ page }) => {
        await page.goto('/dashboard');
        // Either "Your Secrets" title or "No secrets found"
        await expect(
            page.getByText('Your Secrets').or(page.getByText('No secrets found'))
        ).toBeVisible({ timeout: 10000 });
    });
});

test.describe('Dashboard - Account Page', () => {
    test.beforeEach(async ({ page }) => {
        await mockCoreAPIs(page, { authenticated: true });
        await mockDashboardAPIs(page);
    });

    test('renders account page', async ({ page }) => {
        await page.goto('/dashboard/account');
        await expect(page).toHaveURL('/dashboard/account', { timeout: 10000 });
    });

    test('shows username on account page', async ({ page }) => {
        await page.goto('/dashboard/account');
        await expect(page.getByText(MOCK_USER.username)).toBeVisible({ timeout: 10000 });
    });

    test('shows email on account page', async ({ page }) => {
        await page.goto('/dashboard/account');
        await expect(page.getByText(MOCK_USER.email)).toBeVisible({ timeout: 10000 });
    });
});

test.describe('Dashboard - Analytics Page', () => {
    test.beforeEach(async ({ page }) => {
        await mockCoreAPIs(page, { authenticated: true });
        await mockDashboardAPIs(page);

        // Mock the main analytics endpoint with a regex that matches /api/analytics
        // (with or without query string) but NOT /api/analytics/visitors/...
        // Registered AFTER mockCoreAPIs so it takes precedence (last-registered wins).
        await page.route(/\/api\/analytics(\?.*)?$/, async (route) => {
            if (route.request().method() === 'GET') {
                await route.fulfill({
                    status: 200,
                    contentType: 'application/json',
                    body: JSON.stringify({
                        totalSecrets: 42,
                        totalViews: 123,
                        averageViews: 2.9,
                        activeSecrets: 10,
                        expiredSecrets: 5,
                        dailyStats: [],
                        secretTypes: { passwordProtected: 1, ipRestricted: 0, burnable: 2 },
                        expirationStats: { oneHour: 1, oneDay: 5, oneWeekPlus: 10 },
                        secretRequests: { total: 0, fulfilled: 0 },
                        visitorStats: [],
                    }),
                });
            } else {
                await route.continue();
            }
        });

        await page.goto('/');
    });

    test('renders analytics page', async ({ page }) => {
        await page.goto('/dashboard/analytics');
        await expect(page).toHaveURL('/dashboard/analytics', { timeout: 10000 });
    });

    test('shows analytics content', async ({ page }) => {
        await page.goto('/dashboard/analytics');
        // Use heading with exact match to distinguish "Analytics" (h1) from "Visitor Analytics" (h2)
        await expect(page.getByRole('heading', { name: 'Analytics', exact: true })).toBeVisible({ timeout: 10000 });
    });
});

test.describe('Dashboard - Users Page', () => {
    test.beforeEach(async ({ page }) => {
        await mockCoreAPIs(page, { authenticated: true });
        await mockDashboardAPIs(page);
        await page.goto('/');
    });

    test('renders users page', async ({ page }) => {
        await page.goto('/dashboard/users');
        await expect(page).toHaveURL('/dashboard/users', { timeout: 10000 });
    });

    test('shows user management title', async ({ page }) => {
        await page.goto('/dashboard/users');
        await expect(page.getByText('User Management')).toBeVisible({ timeout: 10000 });
    });
});

test.describe('Dashboard - Instance Settings Page', () => {
    test.beforeEach(async ({ page }) => {
        await mockCoreAPIs(page, { authenticated: true });
        await mockDashboardAPIs(page);
        await page.goto('/');
    });

    test('renders instance settings page', async ({ page }) => {
        await page.goto('/dashboard/instance');
        await expect(page).toHaveURL('/dashboard/instance', { timeout: 10000 });
    });

    test('shows instance settings title', async ({ page }) => {
        await page.goto('/dashboard/instance');
        await expect(page.getByText('Instance Settings')).toBeVisible({ timeout: 10000 });
    });
});

test.describe('Dashboard - Invites Page', () => {
    test.beforeEach(async ({ page }) => {
        await mockCoreAPIs(page, { authenticated: true });
        await mockDashboardAPIs(page);
        await page.goto('/');
    });

    test('renders invites page', async ({ page }) => {
        await page.goto('/dashboard/invites');
        await expect(page).toHaveURL('/dashboard/invites', { timeout: 10000 });
    });

    test('shows invite codes title', async ({ page }) => {
        await page.goto('/dashboard/invites');
        // Use heading role to avoid strict-mode violation (subtitle also contains "invite codes")
        await expect(page.getByRole('heading', { name: 'Invite Codes' })).toBeVisible({ timeout: 10000 });
    });
});

test.describe('Dashboard - Secret Requests Page', () => {
    test.beforeEach(async ({ page }) => {
        await mockCoreAPIs(page, { authenticated: true });
        await mockDashboardAPIs(page);
        await page.goto('/');
    });

    test('renders secret requests page', async ({ page }) => {
        await page.goto('/dashboard/secret-requests');
        await expect(page).toHaveURL('/dashboard/secret-requests', { timeout: 10000 });
    });

    test('shows secret requests title', async ({ page }) => {
        await page.goto('/dashboard/secret-requests');
        // Use heading role to avoid strict-mode violation (sidebar link also says "Secret Requests")
        await expect(page.getByRole('heading', { name: 'Secret Requests' })).toBeVisible({ timeout: 10000 });
    });

    test('has Create Request button', async ({ page }) => {
        await page.goto('/dashboard/secret-requests');
        await expect(
            page.getByRole('button', { name: /create/i }).or(
                page.getByRole('link', { name: /create/i })
            )
        ).toBeVisible({ timeout: 10000 });
    });
});

test.describe('Dashboard - Create Secret Request Page', () => {
    test.beforeEach(async ({ page }) => {
        await mockCoreAPIs(page, { authenticated: true });
        await mockDashboardAPIs(page);
        await page.goto('/');
    });

    test('renders create secret request page', async ({ page }) => {
        await page.goto('/dashboard/secret-requests/create');
        await expect(page).toHaveURL('/dashboard/secret-requests/create', { timeout: 10000 });
    });

    test('shows create secret request heading', async ({ page }) => {
        await page.goto('/dashboard/secret-requests/create');
        await expect(page.getByText('Create Secret Request')).toBeVisible({ timeout: 10000 });
    });

    test('has request title input', async ({ page }) => {
        await page.goto('/dashboard/secret-requests/create');
        await expect(
            page.getByPlaceholder(/aws credentials/i).or(
                page.getByLabel(/title/i)
            )
        ).toBeVisible({ timeout: 10000 });
    });

    test('has back button to return to secret requests list', async ({ page }) => {
        await page.goto('/dashboard/secret-requests/create');
        await expect(
            page.getByRole('link', { name: /back/i })
        ).toBeVisible({ timeout: 10000 });
    });
});

test.describe('Dashboard - Navigation Sidebar', () => {
    test.beforeEach(async ({ page }) => {
        await mockCoreAPIs(page, { authenticated: true });
        await mockDashboardAPIs(page);
        // Navigate to root layout first so its loader populates the Zustand store
        // with settings (including requireInviteCode=true).
        await page.goto('/');
        // Then click the Dashboard header link — this uses React Router's client-side
        // navigation, so the Zustand store (and requireInviteCode=true) is preserved.
        await page.getByRole('link', { name: 'Dashboard' }).click();
        await expect(page).toHaveURL('/dashboard', { timeout: 10000 });
    });

    test('shows Secrets navigation item', async ({ page }) => {
        // "Secrets" nav link is in the desktop sidebar
        const secretsLinks = page.getByRole('link', { name: /^secrets$/i });
        await expect(secretsLinks.first()).toBeVisible({ timeout: 10000 });
    });

    test('shows Account navigation item', async ({ page }) => {
        await expect(page.getByRole('link', { name: /account/i })).toBeVisible({ timeout: 10000 });
    });

    test('can navigate to account page from sidebar', async ({ page }) => {
        const accountLink = page.getByRole('link', { name: /account/i });
        await expect(accountLink).toBeVisible({ timeout: 10000 });
        await accountLink.click();
        await expect(page).toHaveURL('/dashboard/account', { timeout: 5000 });
    });

    test('shows Analytics navigation item', async ({ page }) => {
        await expect(
            page.getByRole('link', { name: /analytics/i })
        ).toBeVisible({ timeout: 10000 });
    });

    test('shows Users navigation item', async ({ page }) => {
        await expect(
            page.getByRole('link', { name: /users/i })
        ).toBeVisible({ timeout: 10000 });
    });

    test('shows Invites navigation item', async ({ page }) => {
        // Invites only shows when requireInviteCode is true (which it is in our mock)
        await expect(
            page.getByRole('link', { name: /invite/i }).first()
        ).toBeVisible({ timeout: 10000 });
    });

    test('shows Instance navigation item', async ({ page }) => {
        await expect(
            page.getByRole('link', { name: /instance/i })
        ).toBeVisible({ timeout: 10000 });
    });

    test('shows Secret Requests navigation item', async ({ page }) => {
        await expect(
            page.getByRole('link', { name: /secret requests/i })
        ).toBeVisible({ timeout: 10000 });
    });
});
