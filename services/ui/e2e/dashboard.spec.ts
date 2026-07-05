import { test, expect } from './fixtures'

test.describe('Dashboard', () => {
  test('loads and displays home heading', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('heading', { name: /home/i })).toBeVisible({ timeout: 10_000 })
  })

  test('shows courses widget with data or empty state', async ({ page }) => {
    await page.goto('/')

    // The courses widget shows either the course list or its empty state
    const coursesLabel = page.getByText(/^courses$/i).first()
    const emptyState = page.getByText(/no courses yet/i).first()
    await expect(coursesLabel.or(emptyState).first()).toBeVisible({ timeout: 15_000 })
  })

  test('dashboard widgets render independently', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('heading', { name: /home/i })).toBeVisible({ timeout: 10_000 })

    // At least one widget section resolves out of its loading state
    const anyWidgetContent = page
      .getByText(/recent activity|your courses|^courses$|streak|exams/i)
      .first()
    await expect(anyWidgetContent).toBeVisible({ timeout: 15_000 })
  })
})
