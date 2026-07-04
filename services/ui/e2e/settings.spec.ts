import { test, expect } from './fixtures'

test.describe('Settings Page', () => {
  test('navigates to settings page', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Click Settings in sidebar (desktop)
    await page.setViewportSize({ width: 1280, height: 720 })
    const settingsLink = page.locator('aside a[href="/settings"]')
    await expect(settingsLink).toBeVisible({ timeout: 10_000 })
    await settingsLink.click()
    await expect(page).toHaveURL('/settings', { timeout: 10_000 })

    // Page header should be visible
    await expect(page.getByText('Settings')).toBeVisible({ timeout: 10_000 })
  })

  test('settings sections render correctly', async ({ page }) => {
    await page.goto('/settings')
    await page.waitForLoadState('networkidle')

    // Verify main sections are present
    await expect(page.getByText('Appearance')).toBeVisible({ timeout: 10_000 })
    await expect(page.getByText('AI Provider')).toBeVisible({ timeout: 10_000 })
    await expect(page.getByText('Pipeline Tuning')).toBeVisible({ timeout: 10_000 })

    // Verify theme buttons exist
    await expect(page.getByRole('button', { name: 'Light' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Dark' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'System' })).toBeVisible()

    // Verify save/reset buttons
    await expect(page.getByRole('button', { name: 'Save Settings' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Reset' })).toBeVisible()
  })

  test('dark mode toggle applies dark class', async ({ page }) => {
    await page.goto('/settings')
    await page.waitForLoadState('networkidle')

    // Click the Dark theme button
    const darkBtn = page.getByRole('button', { name: 'Dark' })
    await expect(darkBtn).toBeVisible({ timeout: 10_000 })
    await darkBtn.click()

    // Verify <html> has the dark class
    await expect(page.locator('html')).toHaveClass(/dark/, { timeout: 5_000 })

    // Switch back to light
    const lightBtn = page.getByRole('button', { name: 'Light' })
    await lightBtn.click()
    await expect(page.locator('html')).not.toHaveClass(/dark/, { timeout: 5_000 })
  })

  test('dark mode persists across page reload', async ({ page }) => {
    await page.goto('/settings')
    await page.waitForLoadState('networkidle')

    // Enable dark mode
    const darkBtn = page.getByRole('button', { name: 'Dark' })
    await expect(darkBtn).toBeVisible({ timeout: 10_000 })
    await darkBtn.click()
    await expect(page.locator('html')).toHaveClass(/dark/, { timeout: 5_000 })

    // Verify localStorage was updated
    const storedTheme = await page.evaluate(() => localStorage.getItem('studyaio-theme'))
    expect(storedTheme).toBe('dark')

    // Reload and verify dark mode persists
    await page.reload()
    await page.waitForLoadState('networkidle')
    await expect(page.locator('html')).toHaveClass(/dark/, { timeout: 5_000 })

    // Clean up: reset to light
    const lightBtn = page.getByRole('button', { name: 'Light' })
    await expect(lightBtn).toBeVisible({ timeout: 10_000 })
    await lightBtn.click()
  })
})
