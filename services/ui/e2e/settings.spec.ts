import { test, expect } from './fixtures'

test.describe('Settings Page', () => {
  test('navigates to settings page', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 })
    await page.goto('/')
    await expect(page.getByRole('heading', { name: /home/i })).toBeVisible({ timeout: 10_000 })

    // Click Settings in sidebar (desktop)
    const settingsLink = page.locator('aside a[href="/settings"]')
    await expect(settingsLink).toBeVisible({ timeout: 10_000 })
    await settingsLink.click()
    await expect(page).toHaveURL(/\/settings/, { timeout: 10_000 })

    // Page header should be visible
    await expect(page.getByRole('heading', { name: /settings/i })).toBeVisible({ timeout: 10_000 })
  })

  test('settings sections render as sub-routes', async ({ page }) => {
    await page.goto('/settings')

    // Section rail lists all sections
    await expect(page.getByRole('link', { name: /appearance/i })).toBeVisible({ timeout: 10_000 })
    await expect(page.getByRole('link', { name: /ai providers/i })).toBeVisible()
    await expect(page.getByRole('link', { name: /pipeline/i })).toBeVisible()

    // Default section is Appearance with the theme picker
    await expect(page.getByRole('heading', { name: /appearance/i })).toBeVisible({
      timeout: 10_000,
    })
    const themeGroup = page.getByRole('group', { name: /theme/i })
    await expect(themeGroup.getByRole('button', { name: 'Light' })).toBeVisible()
    await expect(themeGroup.getByRole('button', { name: 'Dark' })).toBeVisible()
    await expect(themeGroup.getByRole('button', { name: 'System' })).toBeVisible()

    // Navigating to another section swaps the content
    await page.getByRole('link', { name: /ai providers/i }).click()
    await expect(page).toHaveURL(/\/settings\/ai/, { timeout: 10_000 })
  })

  test('dark mode toggle applies dark class', async ({ page }) => {
    await page.goto('/settings')

    const themeGroup = page.getByRole('group', { name: /theme/i })
    const darkBtn = themeGroup.getByRole('button', { name: 'Dark' })
    await expect(darkBtn).toBeVisible({ timeout: 10_000 })
    await darkBtn.click()

    // Verify <html> has the dark class
    await expect(page.locator('html')).toHaveClass(/dark/, { timeout: 5_000 })

    // Switch back to light
    const lightBtn = themeGroup.getByRole('button', { name: 'Light' })
    await lightBtn.click()
    await expect(page.locator('html')).not.toHaveClass(/dark/, { timeout: 5_000 })
  })

  test('dark mode persists across page reload', async ({ page }) => {
    await page.goto('/settings')

    const themeGroup = page.getByRole('group', { name: /theme/i })
    const darkBtn = themeGroup.getByRole('button', { name: 'Dark' })
    await expect(darkBtn).toBeVisible({ timeout: 10_000 })
    await darkBtn.click()
    await expect(page.locator('html')).toHaveClass(/dark/, { timeout: 5_000 })

    // Verify localStorage was updated
    const storedTheme = await page.evaluate(() => localStorage.getItem('studyaio-theme'))
    expect(storedTheme).toBe('dark')

    // Reload and verify dark mode persists
    await page.reload()
    await expect(page.locator('html')).toHaveClass(/dark/, { timeout: 5_000 })

    // Clean up: reset to light
    const lightBtn = page
      .getByRole('group', { name: /theme/i })
      .getByRole('button', { name: 'Light' })
    await expect(lightBtn).toBeVisible({ timeout: 10_000 })
    await lightBtn.click()
  })
})
