import { test, expect } from './fixtures'

test.describe('Ask (chat sessions)', () => {
  test('legacy /chat redirects to /ask', async ({ page }) => {
    await page.goto('/chat')
    await expect(page).toHaveURL(/\/ask/, { timeout: 10_000 })
  })

  test('ask page loads with welcome message', async ({ page }) => {
    await page.goto('/ask')
    await page.waitForLoadState('networkidle')

    // Should show the Ask surface or welcome text
    await expect(
      page.getByText(/ask|welcome|conversation|new question|new chat/i).first(),
    ).toBeVisible({ timeout: 10_000 })
  })

  test('new question button is visible', async ({ page }) => {
    await page.goto('/ask')
    await page.waitForLoadState('networkidle')

    const newBtn = page.getByRole('button', { name: /new question|new chat/i }).first()
    await expect(newBtn).toBeVisible({ timeout: 10_000 })
  })

  test('clicking new question creates a session', async ({ page }) => {
    await page.goto('/ask')
    await page.waitForLoadState('networkidle')

    const newBtn = page.getByRole('button', { name: /new question|new chat/i }).first()
    await expect(newBtn).toBeVisible({ timeout: 10_000 })
    await newBtn.click()

    // Should either navigate to a session or show the chat input
    await page.waitForTimeout(2000)
    const url = page.url()
    // URL should contain session parameter or the composer should be visible
    const hasSession = url.includes('session=')
    const hasInput = await page.locator('textarea, input[type="text"]').first().isVisible().catch(() => false)
    expect(hasSession || hasInput).toBeTruthy()
  })
})
