import { test, expect } from './fixtures'

// The PWA service worker would intercept /api/dashboard before page.route can —
// block it so route interception works.
test.use({ serviceWorkers: 'block' })

test.describe('Error handling', () => {
  test('dashboard API failure shows per-widget error states, shell stays, retry recovers', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 720 })

    // Force the dashboard API to fail
    await page.route('**/api/dashboard**', (route) =>
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal Server Error' }),
      }),
    )

    await page.goto('/')

    // Per-widget error states appear (React Query retries twice first)
    const widgetError = page.getByText(/couldn't load/i).first()
    await expect(widgetError).toBeVisible({ timeout: 20_000 })

    // The shell navigation survives the failing page region
    await expect(page.locator('aside')).toBeVisible()
    await expect(page.locator('aside a[href="/upload"]')).toBeVisible()

    // Recovery: stop failing and retry
    await page.unroute('**/api/dashboard**')
    await page.getByRole('button', { name: /retry/i }).first().click()

    await expect(page.getByText(/couldn't load/i)).toHaveCount(0, { timeout: 20_000 })
  })
})
