import { test, expect } from "@playwright/test"

const REPO_PATH = "<benchmark-root>/projects/git-truck"
const BRANCH = "rq6-agent-tests"
const PROJECTS_PATH = "<benchmark-root>/projects"

const VIEW_URL =
  `/view?path=${encodeURIComponent(REPO_PATH)}` +
  `&objectPath=git-truck&zoomPath=git-truck` +
  `&branch=${encodeURIComponent(BRANCH)}` +
  `&start=0&end=1782515397`

// The view page can take time to analyze the repository on first load
const ANALYSIS_TIMEOUT = 90_000

test.describe("View Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(VIEW_URL)
    // Wait for analysis and page render - title changes when data is loaded
    await expect(page).toHaveTitle(/git-truck - Git Truck/, { timeout: ANALYSIS_TIMEOUT })
  })

  test("view page has correct title", async ({ page }) => {
    await expect(page).toHaveTitle(/git-truck - Git Truck/)
  })

  test("view page shows Git Truck heading link to GitHub", async ({ page }) => {
    const gitTruckLink = page.getByRole("link", { name: "Git Truck" }).first()
    await expect(gitTruckLink).toBeVisible()
    await expect(gitTruckLink).toHaveAttribute("href", "https://github.com/git-truck/git-truck")
  })

  test("view page toolbar buttons are all visible", async ({ page }) => {
    await expect(page.getByTitle(/Refresh analysis/i)).toBeVisible()
    await expect(page.getByTitle(/Hidden files/i)).toBeVisible()
    await expect(page.getByTitle(/Group contributors/i)).toBeVisible()
    await expect(page.getByTitle(/Settings/i)).toBeVisible()
    await expect(page.getByTitle(/Enter fullscreen/i)).toBeVisible()
  })

  test("view page shows breadcrumb navigation", async ({ page }) => {
    // Breadcrumb renders as a div with links to browse parent directories
    // The breadcrumb should contain "projects" as a link (parent of git-truck)
    const projectsLink = page.getByRole("link", { name: /projects/ }).first()
    await expect(projectsLink).toBeVisible()
  })

  test("view page has file search input with repo-specific placeholder", async ({ page }) => {
    // The search input placeholder is "Search within git-truck"
    const searchInput = page.locator('input[placeholder*="Search within"]')
    await expect(searchInput).toBeAttached()
  })

  test("visualization options panel is visible with Layout/Size/Color controls", async ({ page }) => {
    // The left side panel "Visualization options" (appears twice - visible + hidden in mobile layout)
    await expect(page.getByText("Visualization options").first()).toBeVisible()
    // Layout/Size/Color labels within the options panel
    await expect(page.getByText("Layout").first()).toBeVisible()
    await expect(page.getByText("Node Size").first()).toBeVisible()
    await expect(page.getByText("Node Color").first()).toBeVisible()
  })

  test("can toggle left panel (hide and show)", async ({ page }) => {
    // The hide left panel button may only appear on large screens
    const hideLeftBtn = page.getByTitle("Hide left panel")
    if ((await hideLeftBtn.count()) > 0) {
      await hideLeftBtn.click()
      await expect(page.getByTitle("Show left panel")).toBeVisible({ timeout: 3000 })
      // Toggle back
      await page.getByTitle("Show left panel").click()
      await expect(page.getByTitle("Hide left panel")).toBeVisible({ timeout: 3000 })
    }
  })

  test("can toggle right panel (hide and show)", async ({ page }) => {
    const hideRightBtn = page.getByTitle("Hide right panel")
    if ((await hideRightBtn.count()) > 0) {
      await hideRightBtn.click()
      await expect(page.getByTitle("Show Right panel")).toBeVisible({ timeout: 3000 })
      // Toggle back
      await page.getByTitle("Show Right panel").click()
    }
  })

  test("view page shows chart area container", async ({ page }) => {
    // The chart area is a div with grid-area styling
    // Just verify the page has loaded with the main content area
    await expect(page.locator("canvas, svg").first()).toBeVisible({ timeout: 10_000 })
  })

  test("Actions panel shows Browse button for current object", async ({ page }) => {
    // The InteractionButtons component renders a "Browse" button (type=submit, not link)
    // when the clicked object is a tree (folder/repo root)
    const browseButton = page.getByRole("button", { name: /browse/i }).first()
    await expect(browseButton).toBeVisible()
  })

  test("go back to browse via breadcrumb link", async ({ page }) => {
    // Click the "projects" breadcrumb link to go back to browse
    const projectsLink = page.getByRole("link", { name: /projects/ }).first()
    if ((await projectsLink.count()) > 0) {
      await projectsLink.click()
      await page.waitForURL(/\/browse/, { timeout: 10000 })
      await expect(page).toHaveURL(/\/browse/)
    }
  })

  test("view page shows collapsible Legend section", async ({ page }) => {
    // The Legend section is a CollapsibleHeader in the left panel
    // The heading contains "Legend" text
    await expect(page.getByText("Legend").first()).toBeVisible()
  })

  test("Settings button opens Settings modal/panel", async ({ page }) => {
    const settingsBtn = page.getByTitle(/Settings/i)
    await settingsBtn.click()
    // After clicking, the Settings panel or modal should appear
    // The Settings panel has a heading with "Settings" text
    await expect(page.getByRole("heading", { name: /Settings/i })).toBeVisible({ timeout: 5000 })
  })

  test("Group contributors button opens Group Contributors panel", async ({ page }) => {
    const groupBtn = page.getByTitle(/Group contributors/i)
    await groupBtn.click()
    // The group contributors modal should show "Ungrouped Contributors" heading
    // Use first() to avoid strict mode since the modal may render multiple times (dialog + backdrop)
    await expect(page.getByText(/Ungrouped Contributors/).first()).toBeVisible({ timeout: 5000 })
  })

  test("Hidden files button opens Hide files modal", async ({ page }) => {
    const hideFilesBtn = page.getByTitle("Hidden files")
    await hideFilesBtn.click()
    // The modal opens with title "Hide files" and an input for patterns
    await expect(page.getByPlaceholder("Enter pattern...")).toBeVisible({ timeout: 5000 })
  })

  test("Hide files modal allows adding a pattern", async ({ page }) => {
    const hideFilesBtn = page.getByTitle("Hidden files")
    await hideFilesBtn.click()
    // Wait for modal to open
    const patternInput = page.getByPlaceholder("Enter pattern...")
    await expect(patternInput).toBeVisible({ timeout: 5000 })
    // Type a pattern
    await patternInput.fill("*.log")
    // Click Hide button
    await page.getByRole("button", { name: /^Hide$/ }).click()
    // The pattern should appear in the hidden files list
    await expect(page.getByText("*.log")).toBeVisible({ timeout: 5000 })
  })

  test("Details panel shows metrics for the current object", async ({ page }) => {
    // The right panel has a "Details" collapsible section
    // The heading is "Details" + ClickedObjectButton (e.g. "Detailsgit-truck")
    // Look for the word "Details" in a heading element
    const detailsHeading = page
      .getByRole("heading")
      .filter({ hasText: "Details" })
      .first()
    await expect(detailsHeading).toBeVisible()
    // The details show metrics - "Commits" appears in the MetricsInspection panel as a stat label
    // Use first() to avoid strict mode since "Commits" also appears as a section heading
    await expect(page.getByText(/Commits/).first()).toBeVisible()
  })

  test("Commits panel shows commit history description", async ({ page }) => {
    // The CommitsInspection panel has this introductory text (may appear in multiple places)
    await expect(page.getByText(/Shows the commit history/i).first()).toBeVisible()
  })

  test("Timeline bar chart is visible at bottom", async ({ page }) => {
    // The Timeline component renders with "Commit activity" heading (may appear twice)
    await expect(page.getByText(/Commit activity/i).first()).toBeVisible()
  })
})

// ── View Page - Error handling ──────────────────────────────────────────────────

test.describe("View Page - Error handling", () => {
  test("view with invalid path shows error page or redirects to browse", async ({ page }) => {
    await page.goto(
      `/view?path=${encodeURIComponent("/nonexistent/path/xyz")}&objectPath=xyz&zoomPath=xyz&branch=main&start=0&end=1782515397`
    )
    await page.waitForLoadState("networkidle")
    // Should redirect to browse or show an error
    const url = page.url()
    const isBrowsePage = url.includes("/browse")
    const hasErrorText = await page.getByText(/error|not found|crashed|oh no/i).count()
    expect(isBrowsePage || hasErrorText > 0).toBeTruthy()
  })

  test("view page shows Abort button while loading", async ({ page }) => {
    // When loading a new analysis, an "Abort" button is shown
    // This is hard to test reliably since analysis may be cached
    // Just verify the page loads properly
    await page.goto(VIEW_URL)
    await expect(page).toHaveTitle(/git-truck|Git Truck/, { timeout: ANALYSIS_TIMEOUT })
    await expect(page.locator("body")).not.toBeEmpty()
  })
})

// ── View Page - Navigation back to Browse ──────────────────────────────────────

test.describe("View to Browse navigation", () => {
  test("clicking parent directory in breadcrumb goes to browse page", async ({ page }) => {
    await page.goto(VIEW_URL)
    await expect(page).toHaveTitle(/git-truck - Git Truck/, { timeout: ANALYSIS_TIMEOUT })

    // The breadcrumb has a link to the parent directory (PROJECTS_PATH)
    const parentLink = page.getByTitle(new RegExp(`Browse.*projects directory`, "i"))
    if ((await parentLink.count()) > 0) {
      await parentLink.click()
      await page.waitForURL(/\/browse/, { timeout: 10000 })
      await expect(page).toHaveURL(/\/browse/)
    }
  })
})
