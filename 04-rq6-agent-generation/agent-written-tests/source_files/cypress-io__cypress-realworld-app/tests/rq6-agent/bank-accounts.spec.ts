import { test, expect } from "@playwright/test";
import { loginViaUi, dismissOnboardingIfPresent } from "./helpers/auth";

// MUI TextField puts data-test on outer wrapper div, not the <input>.
// Use [data-test="..."] input to reach the actual input element.
function getBankInput(page: any, testId: string) {
  return page.locator(`[data-test="${testId}"] input`);
}

test.describe("Bank Accounts", () => {
  test.beforeEach(async ({ page }) => {
    await loginViaUi(page);
    await dismissOnboardingIfPresent(page);
  });

  test("bank accounts page loads and shows existing accounts", async ({ page }) => {
    await page.goto("http://localhost:3000/bankaccounts");
    // Wait for the Create button which appears quickly, then wait for list or empty state
    await page.waitForSelector('[data-test="bankaccount-new"]', { timeout: 10000 });
    // Then wait for the actual list or empty state to load from API
    await page.waitForSelector('[data-test="bankaccount-list"], [data-test="empty-list-header"]', {
      timeout: 15000,
    });
    const hasList = await page.getByTestId("bankaccount-list").isVisible();
    const hasEmpty = await page.locator('[data-test="empty-list-header"]').isVisible();
    expect(hasList || hasEmpty).toBeTruthy();
  });

  test("create bank account button is visible on /bankaccounts", async ({ page }) => {
    await page.goto("http://localhost:3000/bankaccounts");
    await expect(page.getByTestId("bankaccount-new")).toBeVisible({ timeout: 10000 });
  });

  test("clicking create button navigates to /bankaccounts/new", async ({ page }) => {
    await page.goto("http://localhost:3000/bankaccounts");
    await page.getByTestId("bankaccount-new").click({ timeout: 10000 });
    await expect(page).toHaveURL(/\/bankaccounts\/new/);
  });

  test("create bank account form shows all fields", async ({ page }) => {
    await page.goto("http://localhost:3000/bankaccounts/new");
    await expect(page.getByTestId("bankaccount-bankName-input")).toBeVisible({ timeout: 10000 });
    await expect(page.getByTestId("bankaccount-routingNumber-input")).toBeVisible();
    await expect(page.getByTestId("bankaccount-accountNumber-input")).toBeVisible();
    await expect(page.getByTestId("bankaccount-submit")).toBeVisible();
  });

  test("save button is disabled after entering invalid data", async ({ page }) => {
    await page.goto("http://localhost:3000/bankaccounts/new");
    const bankNameInput = getBankInput(page, "bankaccount-bankName-input");
    await bankNameInput.waitFor({ timeout: 10000 });
    // Type short bank name to trigger validation (Formik validateOnChange)
    await bankNameInput.fill("AB");
    await bankNameInput.press("Tab");
    // After validation runs, button should be disabled (all three required fields are invalid/empty)
    await expect(page.getByTestId("bankaccount-submit")).toBeDisabled({ timeout: 5000 });
  });

  test("shows validation for bank name too short (< 5 chars)", async ({ page }) => {
    await page.goto("http://localhost:3000/bankaccounts/new");
    const bankNameInput = getBankInput(page, "bankaccount-bankName-input");
    await bankNameInput.waitFor({ timeout: 10000 });
    await bankNameInput.fill("ABC");
    await bankNameInput.press("Tab");
    await expect(page.getByText(/Must contain at least 5 characters/i)).toBeVisible();
  });

  test("shows validation for routing number wrong length", async ({ page }) => {
    await page.goto("http://localhost:3000/bankaccounts/new");
    const routingInput = getBankInput(page, "bankaccount-routingNumber-input");
    await routingInput.waitFor({ timeout: 10000 });
    await routingInput.fill("12345");
    await routingInput.press("Tab");
    await expect(page.getByText(/Must contain a valid routing number/i)).toBeVisible();
  });

  test("shows validation for account number too short (< 9 digits)", async ({ page }) => {
    await page.goto("http://localhost:3000/bankaccounts/new");
    const accountInput = getBankInput(page, "bankaccount-accountNumber-input");
    await accountInput.waitFor({ timeout: 10000 });
    await accountInput.fill("12345");
    await accountInput.press("Tab");
    await expect(page.getByText(/Must contain at least 9 digits/i)).toBeVisible();
  });

  test("can successfully create a bank account", async ({ page }) => {
    await page.goto("http://localhost:3000/bankaccounts/new");
    const bankNameInput = getBankInput(page, "bankaccount-bankName-input");
    await bankNameInput.waitFor({ timeout: 10000 });

    await bankNameInput.fill("Playwright Bank");
    await getBankInput(page, "bankaccount-routingNumber-input").fill("123456789");
    await getBankInput(page, "bankaccount-accountNumber-input").fill("987654321");

    await expect(page.getByTestId("bankaccount-submit")).toBeEnabled();
    await page.getByTestId("bankaccount-submit").click();

    // After saving, should redirect back to /bankaccounts
    await expect(page).toHaveURL(/\/bankaccounts$/, { timeout: 10000 });
  });

  test("newly created bank account appears in the list", async ({ page }) => {
    await page.goto("http://localhost:3000/bankaccounts/new");
    const bankNameInput = getBankInput(page, "bankaccount-bankName-input");
    await bankNameInput.waitFor({ timeout: 10000 });

    const uniqueBankName = `PW Bank ${Date.now()}`;
    await bankNameInput.fill(uniqueBankName);
    await getBankInput(page, "bankaccount-routingNumber-input").fill("123456789");
    await getBankInput(page, "bankaccount-accountNumber-input").fill("987654321");
    await page.getByTestId("bankaccount-submit").click();

    await expect(page).toHaveURL(/\/bankaccounts$/, { timeout: 10000 });
    await expect(page.getByText(uniqueBankName)).toBeVisible({ timeout: 10000 });
  });

  test("can delete a bank account", async ({ page }) => {
    // First create one so we have something to delete
    await page.goto("http://localhost:3000/bankaccounts/new");
    const bankNameInput = getBankInput(page, "bankaccount-bankName-input");
    await bankNameInput.waitFor({ timeout: 10000 });

    const bankToDelete = `Delete Me ${Date.now()}`;
    await bankNameInput.fill(bankToDelete);
    await getBankInput(page, "bankaccount-routingNumber-input").fill("123456789");
    await getBankInput(page, "bankaccount-accountNumber-input").fill("987654321");
    await page.getByTestId("bankaccount-submit").click();
    await expect(page).toHaveURL(/\/bankaccounts$/, { timeout: 10000 });

    // Find the bank account and delete it
    await expect(page.getByText(bankToDelete)).toBeVisible({ timeout: 10000 });

    // Find the delete button in the same list item
    const deleteBtn = page.getByTestId("bankaccount-delete").last();
    await deleteBtn.click();

    // The bank account should be marked as deleted
    await expect(page.getByText(`${bankToDelete} (Deleted)`)).toBeVisible({ timeout: 10000 });
  });
});
