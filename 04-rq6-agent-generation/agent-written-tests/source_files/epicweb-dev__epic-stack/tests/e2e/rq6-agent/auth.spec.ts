import { test, expect } from '@playwright/test'

test.describe('Login Page', () => {
	test('renders login form with all elements', async ({ page }) => {
		await page.goto('/login')
		await expect(page).toHaveTitle('Login to Epic Notes')
		await expect(page.getByRole('heading', { name: 'Welcome back!' })).toBeVisible()
		await expect(page.getByLabel('Username')).toBeVisible()
		await expect(page.getByLabel('Password')).toBeVisible()
		await expect(page.getByRole('button', { name: /log in/i })).toBeVisible()
		await expect(page.getByLabel('Remember me')).toBeVisible()
		await expect(page.getByRole('link', { name: /forgot password/i })).toBeVisible()
		await expect(page.getByRole('link', { name: /create an account/i })).toBeVisible()
	})

	test('shows validation errors on empty submit', async ({ page }) => {
		await page.goto('/login')
		await page.getByRole('button', { name: /log in/i }).click()
		// Validation errors should appear for required fields
		// The form uses client-side validation via Conform
		await expect(page.getByLabel('Username')).toBeFocused()
	})

	test('shows error with invalid credentials', async ({ page }) => {
		await page.goto('/login')
		await page.getByLabel('Username').fill('nonexistent_user_xyz')
		await page.getByLabel('Password').fill('wrongpassword')
		await page.getByRole('button', { name: /log in/i }).click()
		await expect(page.getByText(/invalid username or password/i)).toBeVisible()
	})

	test('successful login with kody credentials', async ({ page }) => {
		await page.goto('/login')
		await page.getByLabel('Username').fill('kody')
		await page.getByLabel('Password').fill('kodylovesyou')
		await page.getByRole('button', { name: /log in/i }).click()
		// After login, should be redirected away from login page
		await expect(page).not.toHaveURL(/\/login/)
	})

	test('forgot password link navigates to forgot-password page', async ({ page }) => {
		await page.goto('/login')
		await page.getByRole('link', { name: /forgot password/i }).click()
		await expect(page).toHaveURL(/\/forgot-password/)
	})

	test('create account link navigates to signup page', async ({ page }) => {
		await page.goto('/login')
		await page.getByRole('link', { name: /create an account/i }).click()
		await expect(page).toHaveURL(/\/signup/)
	})

	test('remember me checkbox is present and initially unchecked', async ({ page }) => {
		await page.goto('/login')
		// Radix UI checkbox uses button with role="checkbox"
		const checkbox = page.getByRole('checkbox', { name: /remember me/i })
		await expect(checkbox).toBeVisible()
		await expect(checkbox).toHaveAttribute('data-state', 'unchecked')
		// Verify label text is visible
		await expect(page.getByText('Remember me')).toBeVisible()
	})

	test('has passkey login button', async ({ page }) => {
		await page.goto('/login')
		await expect(page.getByRole('button', { name: /login with a passkey/i })).toBeVisible()
	})

	test('has github oauth button', async ({ page }) => {
		await page.goto('/login')
		await expect(page.getByRole('button', { name: /github/i })).toBeVisible()
	})
})

test.describe('Signup Page', () => {
	test('renders signup form with all elements', async ({ page }) => {
		await page.goto('/signup')
		await expect(page).toHaveTitle(/sign up/i)
		await expect(page.getByRole('heading', { name: /start your journey/i })).toBeVisible()
		await expect(page.getByLabel('Email')).toBeVisible()
		await expect(page.getByRole('button', { name: /submit/i })).toBeVisible()
	})

	test('shows email validation error for invalid email', async ({ page }) => {
		await page.goto('/signup')
		await page.getByLabel('Email').fill('not-an-email')
		// Submit to trigger validation
		await page.getByRole('button', { name: /submit/i }).click()
		await expect(page.getByText(/email is invalid/i)).toBeVisible()
	})

	test('shows validation error for empty email on submit', async ({ page }) => {
		await page.goto('/signup')
		await page.getByRole('button', { name: /submit/i }).click()
		// Field should be focused or error shown
		await expect(page.getByLabel('Email')).toBeFocused()
	})

	test('shows error for already registered email', async ({ page }) => {
		await page.goto('/signup')
		await page.getByLabel('Email').fill('kody@kcd.dev')
		await page.getByRole('button', { name: /submit/i }).click()
		await expect(page.getByText(/user already exists/i)).toBeVisible()
	})

	test('has github oauth signup button', async ({ page }) => {
		await page.goto('/signup')
		await expect(page.getByRole('button', { name: /github/i })).toBeVisible()
	})
})

test.describe('Forgot Password Page', () => {
	test('renders forgot password form', async ({ page }) => {
		await page.goto('/forgot-password')
		await expect(page).toHaveTitle(/password recovery/i)
		await expect(page.getByRole('heading', { name: /forgot password/i })).toBeVisible()
		await expect(page.getByLabel('Username or Email')).toBeVisible()
		await expect(page.getByRole('button', { name: /recover password/i })).toBeVisible()
		await expect(page.getByRole('link', { name: /back to login/i })).toBeVisible()
	})

	test('shows error for non-existent user', async ({ page }) => {
		await page.goto('/forgot-password')
		await page.waitForLoadState('networkidle')
		await page.getByLabel('Username or Email').fill('nobody_xyz_123')
		await page.getByRole('button', { name: /recover password/i }).click()
		await page.waitForLoadState('networkidle')
		await expect(page.getByText(/no user exists with this username or email/i)).toBeVisible({ timeout: 10000 })
	})

	test('back to login link navigates to login page', async ({ page }) => {
		await page.goto('/forgot-password')
		await page.getByRole('link', { name: /back to login/i }).click()
		await expect(page).toHaveURL(/\/login/)
	})

	test('shows validation error for empty submit', async ({ page }) => {
		await page.goto('/forgot-password')
		await page.getByRole('button', { name: /recover password/i }).click()
		await expect(page.getByLabel('Username or Email')).toBeFocused()
	})
})

test.describe('Verify Page', () => {
	test('renders verify page with OTP input for onboarding type', async ({ page }) => {
		await page.goto('/verify?type=onboarding&target=test@example.com')
		await expect(page.getByRole('heading', { name: /check your email/i })).toBeVisible()
		await expect(page.getByLabel('Code')).toBeVisible()
		await expect(page.getByRole('button', { name: /submit/i })).toBeVisible()
	})
})

test.describe('Auth Redirect Behavior', () => {
	test('login page redirects authenticated users', async ({ page }) => {
		// First login
		await page.goto('/login')
		await page.getByLabel('Username').fill('kody')
		await page.getByLabel('Password').fill('kodylovesyou')
		await page.getByRole('button', { name: /log in/i }).click()
		await page.waitForURL(/^(?!.*\/login)/)

		// Try to go to login - should redirect away
		await page.goto('/login')
		await expect(page).not.toHaveURL(/\/login/)
	})
})
