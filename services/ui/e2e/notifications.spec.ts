import { test, expect } from './fixtures'

test.describe('Notifications', () => {
  test('bell opens the notification panel', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 })
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    const bell = page.getByRole('button', { name: /notifications/i }).first()
    await expect(bell).toBeVisible({ timeout: 10_000 })
    await bell.click()

    // Panel shows either items, the caught-up empty state, or an error state
    const caughtUp = page.getByText(/you're all caught up/i)
    const markAllRead = page.getByRole('button', { name: /mark all read/i })
    const errored = page.getByText(/notifications couldn't load/i)

    await expect(caughtUp.or(markAllRead).or(errored).first()).toBeVisible({ timeout: 10_000 })
  })
})
