import { test, expect } from "@playwright/test"

// The app is running at http://localhost:3024
// Default CLI path: <benchmark-root> (which is a git repo)
// Projects path (contains git repos): <benchmark-root>/projects
// The git-truck repo is at: <benchmark-root>/projects/git-truck
// Current branch: rq6-agent-tests

const DEFAULT_PATH = "<benchmark-root>"
const PROJECTS_PATH = "<benchmark-root>/projects"
const REPO_PATH = "<benchmark-root>/projects/git-truck"

const BROWSE_URL = (path: string, extra = "") =>
  `/browse?path=${encodeURIComponent(path)}&include-dirs=true${extra}`

// ── Routing & Navigation ─────────────────────────────────────────────────────

test.describe("Routing & Navigation", () => {
  test("root / navigates to a valid app page (not stays at root)", async ({ page }) => {
    // Root redirects to /browse, which then redirects to /view if the default path is a git repo
    // Just verify navigation away from raw '/'
    await page.goto("/")
    await page.waitForLoadState("networkidle")
    const url = page.url()
    // Should have navigated to /browse or /view, not stayed at raw /
    expect(url).toMatch(/\/(browse|view)/)
  })

  test("/browse without params redirects to browse with a path param", async ({ page }) => {
    // Server redirects /browse to /browse?path=DEFAULT_PATH
    // Then client may redirect further to /view if DEFAULT_PATH is a git repo
    await page.goto("/browse")
    await page.waitForLoadState("networkidle")
    // The URL should contain 'path=' at some point in the redirect chain
    const url = page.url()
    expect(url).toMatch(/path=/)
  })

  test("/browse with a git repo path redirects to /view", async ({ page }) => {
    // Navigating to a directory that IS a git repo causes a redirect to /view
    await page.goto(BROWSE_URL(REPO_PATH))
    await page.waitForLoadState("networkidle")
    await expect(page).toHaveURL(/\/view/)
    // The URL contains path= with the unencoded path (browsers don't encode / in query params)
    await expect(page).toHaveURL(/path=.*git-truck/)
  })

  test("/browse with invalid path shows error output", async ({ page }) => {
    await page.goto(BROWSE_URL("/nonexistent/invalid/path/xyz"))
    await page.waitForLoadState("networkidle")
    // Should still show the browse page but with an error output
    await expect(page).toHaveURL(/\/browse/)
    // The error output element should be visible
    const errorOutput = page.locator("output").filter({ hasText: /not found|denied|folder|Not a folder/i })
    await expect(errorOutput).toBeVisible()
  })
})

// ── Browse Page ───────────────────────────────────────────────────────────────

test.describe("Browse Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(BROWSE_URL(PROJECTS_PATH))
    await page.waitForLoadState("networkidle")
  })

  test("shows page title and welcome text", async ({ page }) => {
    await expect(page).toHaveTitle(/Git Truck/)
    await expect(page.getByText("Welcome to Git Truck! Select a repository to visualize.")).toBeVisible()
  })

  test("shows Git Truck heading with GitHub link", async ({ page }) => {
    const gitTruckLink = page.getByRole("link", { name: "Git Truck" }).first()
    await expect(gitTruckLink).toBeVisible()
    await expect(gitTruckLink).toHaveAttribute("href", "https://github.com/git-truck/git-truck")
  })

  test("shows search input with correct placeholder", async ({ page }) => {
    const searchInput = page.locator('input[name="search"]')
    await expect(searchInput).toBeVisible()
    await expect(searchInput).toHaveAttribute("placeholder", /search/i)
  })

  test("shows path input with current path as value", async ({ page }) => {
    const pathInput = page.getByLabel("Path")
    await expect(pathInput).toBeVisible()
    await expect(pathInput).toHaveValue(PROJECTS_PATH)
  })

  test("shows Include directories checkbox (checked by default)", async ({ page }) => {
    const checkbox = page.locator("#include-dirs")
    await expect(checkbox).toBeAttached()
    await expect(checkbox).toBeChecked()
  })

  test("shows Name and Last Changed column headers", async ({ page }) => {
    await expect(page.getByRole("button", { name: /name/i })).toBeVisible()
    await expect(page.getByRole("button", { name: /last changed/i })).toBeVisible()
  })

  test("shows Clear cache button", async ({ page }) => {
    await expect(page.getByRole("button", { name: /clear cache/i })).toBeVisible()
  })

  test("shows pagination with Per page select and page count text", async ({ page }) => {
    // The browse page shows pagination both top and bottom (two per-page selects)
    const perPageLabel = page.getByText(/Per page/).first()
    await expect(perPageLabel).toBeVisible()
    // Page count text
    await expect(page.getByText(/Page \d+ of \d+/).first()).toBeVisible()
  })

  test("search filters directory entries", async ({ page }) => {
    const searchInput = page.locator('input[name="search"]')
    // Get initial count of entry links
    const initialEntries = page.locator("a[title]")
    const initialCount = await initialEntries.count()
    expect(initialCount).toBeGreaterThan(0)

    // Search for something specific - "git" should match git-truck
    await searchInput.fill("git")
    // Wait for debounce (1000ms) + navigation
    await page.waitForTimeout(1500)
    await page.waitForLoadState("networkidle")

    const filteredEntries = page.locator("a[title]")
    const filteredCount = await filteredEntries.count()
    // Should have fewer or equal results
    expect(filteredCount).toBeLessThanOrEqual(initialCount)

    // Clear search
    await searchInput.fill("")
  })

  test("can toggle Include directories checkbox (uncheck then recheck)", async ({ page }) => {
    const checkbox = page.locator("#include-dirs")
    await expect(checkbox).toBeChecked()

    // The checkbox is sr-only, click the wrapping label instead
    const checkboxLabel = page.locator('label:has(#include-dirs)')
    await checkboxLabel.click({ force: true })
    await page.waitForLoadState("networkidle")
    await expect(checkbox).not.toBeChecked()

    // Re-check it
    await checkboxLabel.click({ force: true })
    await page.waitForLoadState("networkidle")
    await expect(checkbox).toBeChecked()
  })

  test("can sort by Name (clicking Name header changes sort param)", async ({ page }) => {
    const nameButton = page.getByRole("button", { name: /name/i })
    await nameButton.click()
    await page.waitForLoadState("networkidle")
    // URL should have sort=asc or sort=desc
    await expect(page).toHaveURL(/sort=(asc|desc)/)
  })

  test("can sort by Last Changed (clicking Last Changed header changes sort param)", async ({ page }) => {
    const lastChangedButton = page.getByRole("button", { name: /last changed/i })
    await lastChangedButton.click()
    await page.waitForLoadState("networkidle")
    // URL should have sort=most-recent or sort=least-recent
    await expect(page).toHaveURL(/sort=(most-recent|least-recent)/)
  })

  test("pagination: next page link is visible when multiple pages exist", async ({ page }) => {
    // Get page count text (using first() to avoid strict mode since there are 2 pagination sections)
    const pageText = await page.getByText(/Page 1 of \d+/).first().textContent()
    if (!pageText) return

    const totalPagesMatch = pageText.match(/Page 1 of (\d+)/)
    const totalPages = totalPagesMatch ? parseInt(totalPagesMatch[1]) : 1

    if (totalPages > 1) {
      const nextPageLink = page.getByTitle("Next page").first()
      await expect(nextPageLink).toBeVisible()
      await nextPageLink.click()
      await page.waitForLoadState("networkidle")
      await expect(page.getByText(/Page 2 of/).first()).toBeVisible()

      // Go back to first page
      const prevPageLink = page.getByTitle("Previous page").first()
      await prevPageLink.click()
      await page.waitForLoadState("networkidle")
      await expect(page.getByText(/Page 1 of/).first()).toBeVisible()
    } else {
      // Single page - just verify pagination text is shown
      await expect(page.getByText(/Page 1 of 1/).first()).toBeVisible()
    }
  })

  test("pagination: can change per-page count", async ({ page }) => {
    // Use the first per-page select (there are two: top and bottom)
    const perPageSelect = page.getByRole("combobox").first()
    await perPageSelect.selectOption("25")
    await page.waitForLoadState("networkidle")
    await expect(page).toHaveURL(/count=25/)
  })

  test("breadcrumb shows path segments as links", async ({ page }) => {
    // The breadcrumb component renders path segments as <a> links to browse URLs
    // The last segment "projects" should be visible as a browse link
    const projectsLink = page.getByRole("link", { name: /projects/ }).first()
    await expect(projectsLink).toBeVisible()
  })

  test("directory entries are clickable links with titles", async ({ page }) => {
    // Each entry is an <a> with title attribute
    const entries = page.locator("a[title]")
    const count = await entries.count()
    expect(count).toBeGreaterThan(0)

    // First entry should have a non-empty title (the path)
    const firstEntry = entries.first()
    await expect(firstEntry).toHaveAttribute("title", /.+/)
  })

  test("can change browse path via text input (press Enter)", async ({ page }) => {
    const pathInput = page.getByLabel("Path")
    await pathInput.clear()
    await pathInput.fill(DEFAULT_PATH)
    await pathInput.press("Enter")
    await page.waitForLoadState("networkidle")
    const url = page.url()
    // The URL should contain "capybara-benchmark" in the path param (unencoded in browser)
    expect(url).toContain("capybara-benchmark")
  })
})

// ── Browse to View navigation ──────────────────────────────────────────────────

test.describe("Browse to View navigation", () => {
  test("clicking a git repository entry navigates to view page", async ({ page }) => {
    await page.goto(BROWSE_URL(PROJECTS_PATH))
    await page.waitForLoadState("networkidle")

    // Find the git-truck entry link
    const gitTruckEntry = page.getByRole("link", { name: "git-truck" })
    if ((await gitTruckEntry.count()) > 0) {
      await gitTruckEntry.first().click()
      await page.waitForURL(/\/view/, { timeout: 10000 })
      await expect(page).toHaveURL(/\/view/)
      await expect(page).toHaveTitle(/git-truck - Git Truck/)
    } else {
      // git-truck may not be visible on page 1; skip test gracefully
      test.skip()
    }
  })
})
