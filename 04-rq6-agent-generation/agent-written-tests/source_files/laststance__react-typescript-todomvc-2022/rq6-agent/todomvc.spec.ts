import { test, expect, type Page } from '@playwright/test'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Clear localStorage so each test starts with an empty todo list. */
async function clearState(page: Page) {
  await page.goto('/')
  await page.evaluate(() => window.localStorage.removeItem('APP_STATE'))
  await page.reload()
}

/** Type a todo text and press Enter to add it. */
async function addTodo(page: Page, text: string) {
  const input = page.getByTestId('new-todo-input-text')
  await input.fill(text)
  await input.press('Enter')
}

// ---------------------------------------------------------------------------
// Pages / Routes
// ---------------------------------------------------------------------------

test.describe('Pages / Routes', () => {
  test('/ - main page renders title and input', async ({ page }) => {
    await clearState(page)
    await expect(page.getByRole('heading', { name: 'todos' })).toBeVisible()
    await expect(page.getByTestId('new-todo-input-text')).toBeVisible()
  })

  test('/active - active filter page loads', async ({ page }) => {
    await clearState(page)
    // Add one todo so the footer + list are rendered
    await addTodo(page, 'Active todo')
    await page.goto('/active')
    await expect(page).toHaveURL('/active')
    await expect(page.getByRole('heading', { name: 'todos' })).toBeVisible()
  })

  test('/completed - completed filter page loads', async ({ page }) => {
    await clearState(page)
    await addTodo(page, 'Some todo')
    await page.goto('/completed')
    await expect(page).toHaveURL('/completed')
    await expect(page.getByRole('heading', { name: 'todos' })).toBeVisible()
  })

  test('unknown route - shows 404 Not Found page', async ({ page }) => {
    await page.goto('/this-route-does-not-exist')
    await expect(
      page.getByRole('heading', { name: 'Page Not Found' }),
    ).toBeVisible()
  })
})

// ---------------------------------------------------------------------------
// Add Todo Flow
// ---------------------------------------------------------------------------

test.describe('Add Todo Flow', () => {
  test.beforeEach(async ({ page }) => {
    await clearState(page)
  })

  test('add todo via Enter key: item appears in list', async ({ page }) => {
    await addTodo(page, 'Buy groceries')
    await expect(page.getByTestId('todo-body-text').first()).toHaveText(
      'Buy groceries',
    )
  })

  test('empty input does not add a todo', async ({ page }) => {
    const input = page.getByTestId('new-todo-input-text')
    await input.fill('   ')
    await input.press('Enter')
    // The todo list section should not exist because there are no todos
    await expect(page.getByTestId('todo-list')).not.toBeVisible()
  })

  test('input cleared after adding todo', async ({ page }) => {
    await addTodo(page, 'Read a book')
    await expect(page.getByTestId('new-todo-input-text')).toHaveValue('')
  })

  test('multiple todos can be added in sequence', async ({ page }) => {
    await addTodo(page, 'First task')
    await addTodo(page, 'Second task')
    await addTodo(page, 'Third task')
    const items = page.getByTestId('todo-body-text')
    await expect(items).toHaveCount(3)
  })
})

// ---------------------------------------------------------------------------
// Toggle Complete / Uncomplete
// ---------------------------------------------------------------------------

test.describe('Todo Item - Toggle Complete / Uncomplete', () => {
  test.beforeEach(async ({ page }) => {
    await clearState(page)
    await addTodo(page, 'Toggle me')
  })

  test('checking checkbox marks todo as completed', async ({ page }) => {
    const checkbox = page.getByTestId('todo-item-complete-check').first()
    await expect(checkbox).not.toBeChecked()
    await checkbox.check()
    await expect(checkbox).toBeChecked()
    // data-testid="todo-item" is on the li itself
    const li = page.getByTestId('todo-item').first()
    await expect(li).toHaveClass(/completed/)
  })

  test('unchecking checkbox restores active state', async ({ page }) => {
    const checkbox = page.getByTestId('todo-item-complete-check').first()
    await checkbox.check()
    await expect(checkbox).toBeChecked()
    await checkbox.uncheck()
    await expect(checkbox).not.toBeChecked()
    // data-testid="todo-item" is on the li itself
    const li = page.getByTestId('todo-item').first()
    await expect(li).not.toHaveClass(/completed/)
  })
})

// ---------------------------------------------------------------------------
// Delete Todo
// ---------------------------------------------------------------------------

test.describe('Todo Item - Delete', () => {
  test.beforeEach(async ({ page }) => {
    await clearState(page)
  })

  test('delete button removes the todo', async ({ page }) => {
    await addTodo(page, 'Delete me')
    await expect(page.getByTestId('todo-body-text').first()).toBeVisible()
    // The destroy button is only visible on CSS hover — hover the item first
    await page.locator('[data-cy="todo-item"]').first().hover()
    await page.getByTestId('delete-todo-btn').first().click()
    await expect(page.getByTestId('todo-body-text')).toHaveCount(0)
  })

  test('deleting one of several todos leaves the rest', async ({ page }) => {
    await addTodo(page, 'Keep this one')
    await addTodo(page, 'Delete this one')
    // Delete-todo-btn click first item (most recently added = "Delete this one")
    await page.locator('[data-cy="todo-item"]').first().hover()
    await page.getByTestId('delete-todo-btn').first().click()
    const remaining = page.getByTestId('todo-body-text')
    await expect(remaining).toHaveCount(1)
    await expect(remaining.first()).toHaveText('Keep this one')
  })
})

// ---------------------------------------------------------------------------
// Edit Todo
// ---------------------------------------------------------------------------

test.describe('Todo Item - Edit', () => {
  test.beforeEach(async ({ page }) => {
    await clearState(page)
    await addTodo(page, 'Original text')
  })

  test('clicking label activates edit input', async ({ page }) => {
    await page.getByTestId('todo-body-text').first().click()
    await expect(page.getByTestId('todo-edit-input').first()).toBeFocused()
  })

  test('edit and save with Enter updates text', async ({ page }) => {
    await page.getByTestId('todo-body-text').first().click()
    const editInput = page.getByTestId('todo-edit-input').first()
    await editInput.fill('Updated text')
    await editInput.press('Enter')
    await expect(page.getByTestId('todo-body-text').first()).toHaveText(
      'Updated text',
    )
  })

  test('edit and press Escape keeps changes', async ({ page }) => {
    await page.getByTestId('todo-body-text').first().click()
    const editInput = page.getByTestId('todo-edit-input').first()
    await editInput.fill('Escape-saved text')
    await editInput.press('Escape')
    await expect(page.getByTestId('todo-body-text').first()).toHaveText(
      'Escape-saved text',
    )
  })

  test('blurring edit input saves the edit', async ({ page }) => {
    await page.getByTestId('todo-body-text').first().click()
    const editInput = page.getByTestId('todo-edit-input').first()
    await editInput.fill('Blur-saved text')
    await editInput.blur()
    await expect(page.getByTestId('todo-body-text').first()).toHaveText(
      'Blur-saved text',
    )
  })

  test('clearing edit text and blurring deletes the todo', async ({ page }) => {
    await page.getByTestId('todo-body-text').first().click()
    const editInput = page.getByTestId('todo-edit-input').first()
    await editInput.fill('')
    await editInput.blur()
    await expect(page.getByTestId('todo-body-text')).toHaveCount(0)
  })
})

// ---------------------------------------------------------------------------
// Footer / Item Count
// ---------------------------------------------------------------------------

test.describe('Footer - Item Count', () => {
  test.beforeEach(async ({ page }) => {
    await clearState(page)
  })

  test('item count shows number of active todos', async ({ page }) => {
    await addTodo(page, 'Task 1')
    await addTodo(page, 'Task 2')
    await addTodo(page, 'Task 3')
    // All are active (uncompleted)
    const countEl = page.locator('[data-cy="remaining-uncompleted-todo-count"]')
    await expect(countEl).toHaveText('3')
  })

  test('item count decrements when a todo is completed', async ({ page }) => {
    await addTodo(page, 'Task A')
    await addTodo(page, 'Task B')
    // Complete one
    await page.getByTestId('todo-item-complete-check').first().check()
    const countEl = page.locator('[data-cy="remaining-uncompleted-todo-count"]')
    await expect(countEl).toHaveText('1')
  })

  test('footer is not shown when todo list is empty', async ({ page }) => {
    // No todos added, footer should not be visible
    await expect(page.locator('footer.footer')).not.toBeVisible()
  })
})

// ---------------------------------------------------------------------------
// Toggle-All
// ---------------------------------------------------------------------------

test.describe('Toggle-All Checkbox', () => {
  test.beforeEach(async ({ page }) => {
    await clearState(page)
    await addTodo(page, 'Alpha')
    await addTodo(page, 'Beta')
    await addTodo(page, 'Gamma')
  })

  test('toggle-all marks all todos as complete', async ({ page }) => {
    await page.getByTestId('toggle-all-btn').check()
    const checkboxes = page.getByTestId('todo-item-complete-check')
    for (const cb of await checkboxes.all()) {
      await expect(cb).toBeChecked()
    }
  })

  test('toggle-all unchecked marks all todos as active', async ({ page }) => {
    // First check all
    await page.getByTestId('toggle-all-btn').check()
    // Now uncheck all
    await page.getByTestId('toggle-all-btn').uncheck()
    const checkboxes = page.getByTestId('todo-item-complete-check')
    for (const cb of await checkboxes.all()) {
      await expect(cb).not.toBeChecked()
    }
  })
})

// ---------------------------------------------------------------------------
// Clear Completed
// ---------------------------------------------------------------------------

test.describe('Clear Completed Button', () => {
  test.beforeEach(async ({ page }) => {
    await clearState(page)
  })

  test('clear-completed button not visible when no todos are complete', async ({
    page,
  }) => {
    await addTodo(page, 'Uncompleted task')
    await expect(
      page.locator('[data-cy="clear-completed-button"]'),
    ).not.toBeVisible()
  })

  test('clear-completed button appears when a todo is completed', async ({
    page,
  }) => {
    await addTodo(page, 'Finish me')
    await page.getByTestId('todo-item-complete-check').first().check()
    await expect(
      page.locator('[data-cy="clear-completed-button"]'),
    ).toBeVisible()
  })

  test('clicking clear-completed removes all completed todos', async ({
    page,
  }) => {
    await addTodo(page, 'Stay active')
    await addTodo(page, 'Mark complete')
    // Complete the most recently added
    await page.getByTestId('todo-item-complete-check').first().check()
    await page.locator('[data-cy="clear-completed-button"]').click()
    const remaining = page.getByTestId('todo-body-text')
    await expect(remaining).toHaveCount(1)
    await expect(remaining.first()).toHaveText('Stay active')
  })
})

// ---------------------------------------------------------------------------
// Filter Links
// ---------------------------------------------------------------------------

test.describe('Filter Links', () => {
  test.beforeEach(async ({ page }) => {
    await clearState(page)
    await addTodo(page, 'Active item')
    await addTodo(page, 'Completed item')
    // Complete the most-recently added item = "Completed item" (added last, appears first)
    await page.getByTestId('todo-item-complete-check').first().check()
  })

  test('All filter shows both active and completed todos', async ({ page }) => {
    await page.locator('[data-cy="all-filter"]').click()
    await expect(page).toHaveURL('/')
    const items = page.getByTestId('todo-body-text')
    await expect(items).toHaveCount(2)
  })

  test('Active filter shows only uncompleted todos', async ({ page }) => {
    await page.locator('[data-cy="active-filter"]').click()
    await expect(page).toHaveURL('/active')
    const items = page.getByTestId('todo-body-text')
    await expect(items).toHaveCount(1)
    await expect(items.first()).toHaveText('Active item')
  })

  test('Completed filter shows only completed todos', async ({ page }) => {
    await page.locator('[data-cy="completed-filter"]').click()
    await expect(page).toHaveURL('/completed')
    const items = page.getByTestId('todo-body-text')
    await expect(items).toHaveCount(1)
    await expect(items.first()).toHaveText('Completed item')
  })

  test('"All" filter link has selected class on / route', async ({ page }) => {
    await page.locator('[data-cy="all-filter"]').click()
    const allLink = page.locator('[data-cy="all-filter"]')
    await expect(allLink).toHaveClass(/selected/)
    await expect(page.locator('[data-cy="active-filter"]')).not.toHaveClass(
      /selected/,
    )
    await expect(page.locator('[data-cy="completed-filter"]')).not.toHaveClass(
      /selected/,
    )
  })

  test('"Active" filter link has selected class on /active route', async ({
    page,
  }) => {
    await page.locator('[data-cy="active-filter"]').click()
    await expect(page.locator('[data-cy="active-filter"]')).toHaveClass(
      /selected/,
    )
    await expect(page.locator('[data-cy="all-filter"]')).not.toHaveClass(
      /selected/,
    )
  })

  test('"Completed" filter link has selected class on /completed route', async ({
    page,
  }) => {
    await page.locator('[data-cy="completed-filter"]').click()
    await expect(page.locator('[data-cy="completed-filter"]')).toHaveClass(
      /selected/,
    )
    await expect(page.locator('[data-cy="all-filter"]')).not.toHaveClass(
      /selected/,
    )
  })
})

// ---------------------------------------------------------------------------
// Persistence
// ---------------------------------------------------------------------------

test.describe('Persistence', () => {
  test('todos survive a page reload', async ({ page }) => {
    await clearState(page)
    await addTodo(page, 'Persistent task')
    await page.reload()
    await expect(page.getByTestId('todo-body-text').first()).toHaveText(
      'Persistent task',
    )
  })

  test('completed state survives a page reload', async ({ page }) => {
    await clearState(page)
    await addTodo(page, 'Complete and persist')
    await page.getByTestId('todo-item-complete-check').first().check()
    await page.reload()
    await expect(
      page.getByTestId('todo-item-complete-check').first(),
    ).toBeChecked()
  })
})
