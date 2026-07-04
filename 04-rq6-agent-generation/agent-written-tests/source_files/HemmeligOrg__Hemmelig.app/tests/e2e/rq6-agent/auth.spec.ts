import { expect, test } from '@playwright/test';
import { mockCoreAPIs } from './helpers/api-mocks';

test.describe('Login Page', () => {
    test.beforeEach(async ({ page }) => {
        await mockCoreAPIs(page);
        await page.goto('/login');
    });

    test('renders login page with correct title', async ({ page }) => {
        await expect(page.getByRole('heading', { name: /sign in/i }).first()).toBeVisible();
    });

    test('shows welcome back subtitle', async ({ page }) => {
        await expect(page.getByText(/welcome back/i)).toBeVisible();
    });

    test('has username input field', async ({ page }) => {
        const usernameInput = page.getByPlaceholder(/enter your username/i);
        await expect(usernameInput).toBeVisible();
    });

    test('has password input field', async ({ page }) => {
        const passwordInput = page.getByPlaceholder(/enter your password/i);
        await expect(passwordInput).toBeVisible();
        await expect(passwordInput).toHaveAttribute('type', 'password');
    });

    test('has Sign In submit button', async ({ page }) => {
        const signInBtn = page.getByRole('button', { name: /sign in/i });
        await expect(signInBtn).toBeVisible();
    });

    test('password visibility toggle shows and hides password', async ({ page }) => {
        const passwordInput = page.getByPlaceholder(/enter your password/i);
        await passwordInput.fill('mypassword123');

        // Find visibility toggle button
        const toggleBtn = page.locator('button[type="button"]').filter({ has: page.locator('svg') }).first();
        await expect(passwordInput).toHaveAttribute('type', 'password');

        // Click the toggle to show password
        await toggleBtn.click();
        await expect(passwordInput).toHaveAttribute('type', 'text');

        // Click again to hide
        await toggleBtn.click();
        await expect(passwordInput).toHaveAttribute('type', 'password');
    });

    test('can type in username field', async ({ page }) => {
        const usernameInput = page.getByPlaceholder(/enter your username/i);
        await usernameInput.fill('testuser');
        await expect(usernameInput).toHaveValue('testuser');
    });

    test('can type in password field', async ({ page }) => {
        const passwordInput = page.getByPlaceholder(/enter your password/i);
        await passwordInput.fill('password123');
        await expect(passwordInput).toHaveValue('password123');
    });

    test('shows error when login fails', async ({ page }) => {
        // Mock failed login
        await page.route('**/api/auth/sign-in/username', async (route) => {
            await route.fulfill({
                status: 401,
                contentType: 'application/json',
                body: JSON.stringify({ error: { message: 'Invalid credentials' } }),
            });
        });

        await page.getByPlaceholder(/enter your username/i).fill('wronguser');
        await page.getByPlaceholder(/enter your password/i).fill('wrongpass');
        await page.getByRole('button', { name: /sign in/i }).click();

        // Error modal or message should appear
        await expect(
            page.getByText(/login failed/i).or(page.getByText(/invalid/i)).or(page.getByText(/error/i)).first()
        ).toBeVisible({ timeout: 5000 });
    });

    test('successful login redirects to dashboard', async ({ page }) => {
        // Mock successful login
        await page.route('**/api/auth/sign-in/username', async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    token: 'test-token',
                    user: {
                        id: 'user1',
                        username: 'testuser',
                        email: 'test@test.com',
                        name: 'Test User',
                        role: 'user',
                    },
                    session: { id: 'session1', userId: 'user1' },
                }),
            });
        });

        // Mock dashboard loader - after login, session should be available
        await page.route('**/api/auth/get-session**', async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    session: { id: 'session1', userId: 'user1' },
                    user: {
                        id: 'user1',
                        username: 'testuser',
                        email: 'test@test.com',
                        name: 'Test User',
                        role: 'user',
                        twoFactorEnabled: false,
                        emailVerified: true,
                        banned: false,
                    },
                }),
            });
        });

        await page.route('**/api/secrets', async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify([]),
            });
        });

        await page.getByPlaceholder(/enter your username/i).fill('testuser');
        await page.getByPlaceholder(/enter your password/i).fill('password123');
        await page.getByRole('button', { name: /sign in/i }).click();

        await expect(page).toHaveURL('/dashboard', { timeout: 10000 });
    });

    test('has link to register page', async ({ page }) => {
        const signUpLink = page.getByRole('link', { name: /sign up/i });
        await expect(signUpLink).toBeVisible();
    });
});

test.describe('Register Page', () => {
    test.beforeEach(async ({ page }) => {
        await mockCoreAPIs(page);
        await page.goto('/register');
    });

    test('renders register page with correct title', async ({ page }) => {
        await expect(
            page.getByRole('heading', { name: /create account/i }).first()
        ).toBeVisible();
    });

    test('shows join hemmelig subtitle', async ({ page }) => {
        await expect(page.getByText(/join hemmelig/i)).toBeVisible();
    });

    test('has username input field', async ({ page }) => {
        const usernameInput = page.getByPlaceholder(/choose a username/i);
        await expect(usernameInput).toBeVisible();
    });

    test('has email input field', async ({ page }) => {
        const emailInput = page.getByPlaceholder(/enter your email/i);
        await expect(emailInput).toBeVisible();
        await expect(emailInput).toHaveAttribute('type', 'email');
    });

    test('has password input field', async ({ page }) => {
        const passwordInput = page.getByPlaceholder(/create a password/i);
        await expect(passwordInput).toBeVisible();
        await expect(passwordInput).toHaveAttribute('type', 'password');
    });

    test('has confirm password input field', async ({ page }) => {
        const confirmInput = page.getByPlaceholder(/confirm your password/i);
        await expect(confirmInput).toBeVisible();
    });

    test('has Create Account submit button', async ({ page }) => {
        const createBtn = page.getByRole('button', { name: /create account/i });
        await expect(createBtn).toBeVisible();
    });

    test('password strength indicator appears when typing password', async ({ page }) => {
        const passwordInput = page.getByPlaceholder(/create a password/i);
        await passwordInput.fill('weak');
        await expect(page.getByText(/password strength/i)).toBeVisible();
    });

    test('shows very weak for short password', async ({ page }) => {
        const passwordInput = page.getByPlaceholder(/create a password/i);
        await passwordInput.fill('abc');
        await expect(page.getByText(/very weak/i)).toBeVisible();
    });

    test('shows strong for complex password', async ({ page }) => {
        const passwordInput = page.getByPlaceholder(/create a password/i);
        await passwordInput.fill('MyStr0ng!Pass#2024');
        await expect(page.getByText(/strong/i)).toBeVisible();
    });

    test('shows passwords match when passwords are identical', async ({ page }) => {
        await page.getByPlaceholder(/create a password/i).fill('MyPassword123!');
        await page.getByPlaceholder(/confirm your password/i).fill('MyPassword123!');
        await expect(page.getByText(/passwords match/i)).toBeVisible();
    });

    test('shows passwords do not match when passwords differ', async ({ page }) => {
        await page.getByPlaceholder(/create a password/i).fill('MyPassword123!');
        await page.getByPlaceholder(/confirm your password/i).fill('DifferentPassword456!');
        await expect(page.getByText(/passwords do not match/i)).toBeVisible();
    });

    test('Create Account button disabled when passwords do not match', async ({ page }) => {
        await page.getByPlaceholder(/create a password/i).fill('password123');
        await page.getByPlaceholder(/confirm your password/i).fill('different123');
        const createBtn = page.getByRole('button', { name: /create account/i });
        await expect(createBtn).toBeDisabled();
    });

    test('has link to login page', async ({ page }) => {
        const signInLink = page.getByRole('link', { name: /sign in/i });
        await expect(signInLink).toBeVisible();
    });

    test('can fill out the entire registration form', async ({ page }) => {
        await page.getByPlaceholder(/choose a username/i).fill('newuser');
        await page.getByPlaceholder(/enter your email/i).fill('newuser@example.com');
        await page.getByPlaceholder(/create a password/i).fill('SecurePass123!');
        await page.getByPlaceholder(/confirm your password/i).fill('SecurePass123!');
        await expect(page.getByText(/passwords match/i)).toBeVisible();
        const createBtn = page.getByRole('button', { name: /create account/i });
        await expect(createBtn).toBeEnabled();
    });

    test('shows error when username already exists', async ({ page }) => {
        // Mock invite code validation to succeed (requireInviteCode=true in mock settings)
        await page.route('**/api/invites/public/validate**', async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({ valid: true }),
            });
        });

        await page.route('**/api/auth/sign-up/email', async (route) => {
            await route.fulfill({
                status: 422,
                contentType: 'application/json',
                body: JSON.stringify({
                    code: 'USER_ALREADY_EXISTS',
                    message: 'User with this email already exists',
                }),
            });
        });

        // Fill all required fields. Use exact placeholder text and skip invite code
        // gracefully if requireInviteCode is false in the running instance settings.
        await page.getByPlaceholder(/choose a username/i).fill('existinguser');
        await page.getByPlaceholder(/enter your email/i).fill('existing@example.com');
        await page.getByPlaceholder(/create a password/i).fill('Password123!');
        await page.getByPlaceholder(/confirm your password/i).fill('Password123!');

        // Fill invite code if present (shown when requireInviteCode=true in mock settings).
        // Use fill() which auto-waits for the element to be actionable.
        const inviteCodeInput = page.getByPlaceholder('Enter your invite code');
        const inviteCodeCount = await inviteCodeInput.count();
        if (inviteCodeCount > 0) {
            await inviteCodeInput.fill('TESTCODE');
        }

        await page.getByRole('button', { name: /create account/i }).click();

        await expect(
            page.getByText(/already exists/i).or(page.getByText(/sign in instead/i))
        ).toBeVisible({ timeout: 8000 });
    });
});

test.describe('Verify 2FA Page', () => {
    test.beforeEach(async ({ page }) => {
        await mockCoreAPIs(page);
        await page.goto('/verify-2fa');
    });

    test('renders 2FA page with title', async ({ page }) => {
        await expect(
            page.getByRole('heading', { name: /two-factor/i })
        ).toBeVisible();
    });

    test('shows 6-digit code entry description', async ({ page }) => {
        await expect(page.getByText(/6-digit/i)).toBeVisible();
    });

    test('has verify button', async ({ page }) => {
        await expect(page.getByRole('button', { name: /verify/i })).toBeVisible();
    });

    test('has back to login link', async ({ page }) => {
        await expect(page.getByRole('link', { name: /back to login/i })).toBeVisible();
    });

    test('back to login navigates to /login', async ({ page }) => {
        await page.getByRole('link', { name: /back to login/i }).click();
        await expect(page).toHaveURL('/login');
    });
});

test.describe('Setup Page', () => {
    test('redirects to / when app is already set up', async ({ page }) => {
        await mockCoreAPIs(page); // mocks needsSetup: false
        await page.goto('/setup');
        // Should redirect away from setup since needsSetup=false
        await expect(page).toHaveURL('/', { timeout: 5000 });
    });

    test('renders setup form when app needs setup', async ({ page }) => {
        // Override setup status to indicate setup is needed
        await page.route('**/api/setup/status', async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({ needsSetup: true }),
            });
        });

        await page.goto('/setup');

        await expect(page.getByRole('heading', { name: /welcome to hemmelig/i })).toBeVisible();
        await expect(page.getByPlaceholder(/enter your full name/i)).toBeVisible();
        await expect(page.getByPlaceholder(/choose a username/i)).toBeVisible();
        await expect(page.getByPlaceholder(/enter your email/i)).toBeVisible();
        await expect(page.getByRole('button', { name: /create admin account/i })).toBeVisible();
    });
});
