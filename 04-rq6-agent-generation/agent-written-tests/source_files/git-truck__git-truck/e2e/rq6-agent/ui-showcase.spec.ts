import { test, expect } from "@playwright/test"

test.describe("UI Showcase Page (/ui)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/ui")
    await page.waitForLoadState("networkidle")
  })

  test("has correct title", async ({ page }) => {
    await expect(page).toHaveTitle(/Git Truck/)
  })

  test("shows UI Components heading", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "UI Components", level: 1 })).toBeVisible()
  })

  test("shows Default Card section", async ({ page }) => {
    // The card has h2 with class card__title
    await expect(page.getByRole("heading", { name: "Default Card", exact: true })).toBeVisible()
    await expect(page.getByText("This is a simple card with some text content.")).toBeVisible()
  })

  test("shows Card with Header section", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Card with Header", exact: true })).toBeVisible()
    await expect(page.getByText("Card with header, subtitle, and content.")).toBeVisible()
  })

  test("shows Buttons section with active button variants", async ({ page }) => {
    // Use exact: true to avoid matching "Disabled Buttons"
    await expect(page.getByRole("heading", { name: "Buttons", exact: true })).toBeVisible()
    // Various button variants present in the Buttons card (non-disabled)
    await expect(page.getByRole("button", { name: "Default" }).first()).toBeVisible()
    await expect(page.getByRole("button", { name: "Primary" }).first()).toBeVisible()
    await expect(page.getByRole("button", { name: "Danger" }).first()).toBeVisible()
    await expect(page.getByRole("button", { name: "Primary Outlined" }).first()).toBeVisible()
    await expect(page.getByRole("button", { name: "Danger Text" }).first()).toBeVisible()
  })

  test("shows Disabled Buttons section", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Disabled Buttons", exact: true })).toBeVisible()
    // Find disabled buttons
    const disabledButtons = page.getByRole("button", { disabled: true })
    const count = await disabledButtons.count()
    expect(count).toBeGreaterThan(0)
  })

  test("shows Inputs & Labels section with input and select", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Inputs & Labels", exact: true })).toBeVisible()
    const input = page.getByPlaceholder("Type here...")
    await expect(input).toBeVisible()
    // Can type in the input
    await input.fill("test input")
    await expect(input).toHaveValue("test input")
    // Select element with "Option 1" - use ID selector to avoid strict mode violation
    const select = page.locator("#select1")
    await expect(select).toBeVisible()
    await expect(select).toHaveValue("Option 1")
  })

  test("shows LoadingIndicator section", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "LoadingIndicator", exact: true })).toBeVisible()
    await expect(page.getByText("Loading something...")).toBeVisible()
  })

  test("shows Slider section with round handles and range display", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Slider, round handles", exact: true })).toBeVisible()
    // The slider shows "Selected window" text (may appear twice for two sliders)
    await expect(page.getByText(/Selected window/i).first()).toBeVisible()
    // Start and End labels
    await expect(page.getByText(/Start: \d+%/).first()).toBeVisible()
    await expect(page.getByText(/End: \d+%/).first()).toBeVisible()
  })

  test("shows Slider section with square handles", async ({ page }) => {
    // Note: source has typo "qquare" but we use exact heading text
    await expect(page.getByRole("heading", { name: /Slider.*[Hh]andles/i }).nth(1)).toBeVisible()
  })

  test("shows IconRadioGroup section with radio options", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "IconRadioGroup", exact: true })).toBeVisible()
    // HeadlessUI RadioGroup renders options with role="radio"
    // The group has options A=Alpha, B=Beta, C=Gamma
    await expect(page.getByRole("radio", { name: /Alpha/i }).first()).toBeVisible()
    await expect(page.getByRole("radio", { name: /Beta/i }).first()).toBeVisible()
    await expect(page.getByRole("radio", { name: /Gamma/i }).first()).toBeVisible()
  })

  test("IconRadioGroup shows initially selected option (Alpha)", async ({ page }) => {
    // The demo uses defaultValue="A" so Alpha should be checked initially
    // HeadlessUI Radio sets data-checked on the checked item
    const alphaOption = page.getByRole("radio", { name: /Alpha/i }).first()
    await expect(alphaOption).toBeVisible()
    // Alpha should have data-checked attribute since it's the default
    await expect(alphaOption).toHaveAttribute("data-checked", "")
  })

  test("shows Breadcrumb section", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Breadcrumb", exact: true })).toBeVisible()
  })

  test("shows Tooltip Demo section", async ({ page }) => {
    await expect(page.getByRole("heading", { name: /Tooltip/i })).toBeVisible()
    await expect(page.getByText("Hover over the button to show tooltip:")).toBeVisible()
  })

  test("shows multiple Git Truck info components", async ({ page }) => {
    // The /ui page has 3 GitTruckInfo demo cards
    const gitTruckLinks = page.getByRole("link", { name: "Git Truck" })
    const count = await gitTruckLinks.count()
    expect(count).toBeGreaterThanOrEqual(1)
    // Check the first one is visible with GitHub link
    await expect(gitTruckLinks.first()).toBeVisible()
    await expect(gitTruckLinks.first()).toHaveAttribute("href", "https://github.com/git-truck/git-truck")
  })

  test("shows Revision Select with branch options", async ({ page }) => {
    // RevisionSelect renders with title="Change branch" on the container div
    const revisionContainer = page.getByTitle("Change branch").first()
    await expect(revisionContainer).toBeVisible()
    // The select inside exists in the DOM (may be visually overlaid/styled)
    const revisionSelect = revisionContainer.locator("select")
    await expect(revisionSelect).toBeAttached()
    // The "main" branch option should be available
    await expect(revisionSelect).toHaveValue("main")
  })
})
