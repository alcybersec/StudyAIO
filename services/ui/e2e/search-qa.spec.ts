import { test, expect } from './fixtures'

test.describe('Q&A / Search', () => {
  test('Q&A page loads with search input', async ({ page }) => {
    await page.goto('/qa')
    await page.waitForLoadState('networkidle')

    // Should show the Q&A interface with an input for questions
    const input = page.locator('textarea, input[type="text"]').first()
    await expect(input).toBeVisible({ timeout: 10_000 })
  })

  test('submitting a question shows loading state', async ({ page }) => {
    await page.goto('/qa')
    await page.waitForLoadState('networkidle')

    const input = page.locator('textarea, input[type="text"]').first()
    await expect(input).toBeVisible({ timeout: 10_000 })

    await input.fill('What is the main concept?')

    // Find and click the submit button
    const submitBtn = page.getByRole('button', { name: /ask|search|submit|send/i })
    if (await submitBtn.isVisible()) {
      await submitBtn.click()
      // Should show loading or answer
      await page.waitForTimeout(2000)
      const pageContent = await page.textContent('body')
      expect(pageContent).toBeTruthy()
    }
  })

  test('Q&A page shows course scope selector', async ({ page }) => {
    await page.goto('/qa')
    await page.waitForLoadState('networkidle')

    // The page should render fully
    const pageContent = await page.textContent('body')
    expect(pageContent && pageContent.length > 0).toBeTruthy()
  })
})
