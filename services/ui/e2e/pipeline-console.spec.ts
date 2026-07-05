import { test, expect } from './fixtures'

test.describe('Pipeline console', () => {
  test('upload page shows dropzone and processing section', async ({ page }) => {
    await page.goto('/upload')
    await expect(page.getByRole('heading', { name: /upload/i })).toBeVisible({ timeout: 10_000 })

    // Demo accounts have uploads disabled — different surface, still valid
    const demoDisabled = await page
      .getByText(/uploads disabled in demo/i)
      .isVisible()
      .catch(() => false)
    if (demoDisabled) {
      test.skip()
      return
    }

    // Dropzone with file input
    await expect(page.getByText(/drop lecture files here/i)).toBeVisible()
    await expect(page.locator('input[type="file"]').first()).toBeAttached()

    // Processing section (live console) is present — populated or empty
    await expect(page.getByText(/processing now/i)).toBeVisible()
    const hasEmpty = await page
      .getByText(/nothing processing/i)
      .isVisible()
      .catch(() => false)
    const hasStageRail = await page
      .getByRole('list', { name: /pipeline stages/i })
      .first()
      .isVisible()
      .catch(() => false)
    expect(hasEmpty || hasStageRail).toBeTruthy()
  })
})
