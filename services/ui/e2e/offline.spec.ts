import { test, expect } from './fixtures'

test.describe('Offline handling', () => {
  test('offline banner appears when connection drops and clears on reconnect', async ({
    page,
    context,
  }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    const banner = page.getByText(/you're offline/i)
    await expect(banner).toBeHidden()

    await context.setOffline(true)
    await expect(banner).toBeVisible({ timeout: 10_000 })

    await context.setOffline(false)
    // Banner clears (a brief "back online — syncing" state may show first)
    await expect(banner).toBeHidden({ timeout: 15_000 })
    await expect(page.getByText(/back online/i)).toBeHidden({ timeout: 15_000 })
  })
})
