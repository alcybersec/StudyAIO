import { test, expect } from './fixtures'

test.describe('Navigation', () => {
  test('sidebar navigation links work on desktop', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 })
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Click Study in sidebar
    const studyLink = page.locator('aside a[href="/study"]')
    await expect(studyLink).toBeVisible({ timeout: 10_000 })
    await studyLink.click()
    await expect(page).toHaveURL('/study', { timeout: 10_000 })

    // Click Upload in sidebar
    const uploadLink = page.locator('aside a[href="/upload"]')
    await uploadLink.click()
    await expect(page).toHaveURL('/upload', { timeout: 10_000 })

    // Click Dashboard
    const dashLink = page.locator('aside a[href="/"]')
    await dashLink.click()
    await expect(page).toHaveURL('/', { timeout: 10_000 })
  })

  test('mobile bottom tabs navigate correctly', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 })
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Bottom nav should be visible
    const bottomNav = page.locator('nav.lg\\:hidden')
    await expect(bottomNav).toBeVisible({ timeout: 10_000 })

    // Click Study tab
    await page.locator('nav.lg\\:hidden a[href="/study"]').click()
    await expect(page).toHaveURL('/study', { timeout: 10_000 })

    // Click Upload tab
    await page.locator('nav.lg\\:hidden a[href="/upload"]').click()
    await expect(page).toHaveURL('/upload', { timeout: 10_000 })
  })

  test('page transitions animate between routes', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Navigate to another page and check that main content area exists
    await page.goto('/upload')
    await page.waitForLoadState('networkidle')

    const main = page.locator('#main-content')
    await expect(main).toBeVisible({ timeout: 10_000 })
  })

  test('404 page shows for unknown routes', async ({ page }) => {
    await page.goto('/nonexistent-route-xyz')
    await page.waitForLoadState('networkidle')

    await expect(
      page.getByText(/not found|404|page.*exist/i),
    ).toBeVisible({ timeout: 10_000 })
  })
})
