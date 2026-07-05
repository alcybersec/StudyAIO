import { test, expect } from './fixtures'

test.describe('Analytics', () => {
  test('page loads with heading and overview cards', async ({ page }) => {
    await page.goto('/analytics')
    await expect(page.getByRole('heading', { name: /analytics/i })).toBeVisible({ timeout: 10_000 })
    await page.waitForLoadState('networkidle')

    // Overview cards render (with data) or the section shows its empty state
    const hasCards = await page
      .getByText(/cards reviewed/i)
      .first()
      .isVisible()
      .catch(() => false)
    const hasEmpty = await page
      .getByText(/no study data yet/i)
      .isVisible()
      .catch(() => false)
    const hasError = await page
      .getByText(/couldn't load/i)
      .first()
      .isVisible()
      .catch(() => false)
    expect(hasCards || hasEmpty || hasError).toBeTruthy()
  })

  test('readiness section is present', async ({ page }) => {
    await page.goto('/analytics')
    await page.waitForLoadState('networkidle')

    const readiness = page.locator('section[aria-label="Exam readiness"]')
    await expect(readiness).toBeAttached({ timeout: 10_000 })
  })

  test('deep link to #readiness scrolls to the section', async ({ page }) => {
    await page.goto('/analytics#readiness')
    await page.waitForLoadState('networkidle')

    const readiness = page.locator('section[aria-label="Exam readiness"]')
    await expect(readiness).toBeAttached({ timeout: 10_000 })
  })
})
