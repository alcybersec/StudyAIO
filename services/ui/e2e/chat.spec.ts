import { test, expect } from './fixtures'

test.describe('Chat', () => {
  test('chat page loads with welcome message', async ({ page }) => {
    await page.goto('/chat')
    await page.waitForLoadState('networkidle')

    // Should show chat heading or welcome text
    await expect(
      page.getByText(/chat|welcome|conversation|new chat/i),
    ).toBeVisible({ timeout: 10_000 })
  })

  test('new chat button is visible', async ({ page }) => {
    await page.goto('/chat')
    await page.waitForLoadState('networkidle')

    const newChatBtn = page.getByRole('button', { name: /new chat/i })
    await expect(newChatBtn).toBeVisible({ timeout: 10_000 })
  })

  test('clicking new chat creates a session', async ({ page }) => {
    await page.goto('/chat')
    await page.waitForLoadState('networkidle')

    const newChatBtn = page.getByRole('button', { name: /new chat/i })
    await expect(newChatBtn).toBeVisible({ timeout: 10_000 })
    await newChatBtn.click()

    // Should either navigate to a session or show the chat input
    await page.waitForTimeout(2000)
    const url = page.url()
    // URL should contain session parameter or the chat interface should be visible
    const hasSession = url.includes('session=')
    const hasInput = await page.locator('textarea, input[type="text"]').isVisible().catch(() => false)
    expect(hasSession || hasInput).toBeTruthy()
  })
})
