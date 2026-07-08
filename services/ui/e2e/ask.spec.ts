import { test, expect } from './fixtures'

test.describe('Ask (merged Q&A)', () => {
  test('legacy /qa redirects to /ask', async ({ page }) => {
    await page.goto('/qa')
    await expect(page).toHaveURL(/\/ask/, { timeout: 10_000 })
  })

  test('ask page shows the composer', async ({ page }) => {
    await page.goto('/ask')
    await page.waitForLoadState('networkidle')

    // The composer input should be visible (session may need creating first)
    const newBtn = page.getByRole('button', { name: /new question|new chat/i }).first()
    if (await newBtn.isVisible().catch(() => false)) {
      await newBtn.click()
      await page.waitForTimeout(1000)
    }
    const input = page.locator('textarea, input[type="text"]').first()
    await expect(input).toBeVisible({ timeout: 10_000 })
  })

  test('composer offers course scoping', async ({ page }) => {
    await page.goto('/ask')
    await page.waitForLoadState('networkidle')

    const newBtn = page.getByRole('button', { name: /new question|new chat/i }).first()
    if (await newBtn.isVisible().catch(() => false)) {
      await newBtn.click()
      await page.waitForTimeout(1000)
    }

    // Scope affordance on the composer (chips added via "+ scope")
    await expect(page.getByRole('button', { name: /scope/i }).first()).toBeVisible({
      timeout: 10_000,
    })
  })
})
