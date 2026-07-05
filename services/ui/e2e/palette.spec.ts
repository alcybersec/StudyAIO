import { test, expect } from './fixtures'

test.describe('Command palette', () => {
  test('opens with Ctrl+K and shows search input', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    await page.keyboard.press('ControlOrMeta+k')

    const input = page.getByRole('combobox', { name: /search commands/i })
    await expect(input).toBeVisible({ timeout: 10_000 })
    await expect(input).toHaveAttribute('placeholder', /search or jump/i)

    // Actions section is listed
    await expect(page.getByText(/^actions$/i).first()).toBeVisible()

    // Escape closes it
    await page.keyboard.press('Escape')
    await expect(input).toBeHidden()
  })

  test('navigation action navigates to upload', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    await page.keyboard.press('ControlOrMeta+k')
    const input = page.getByRole('combobox', { name: /search commands/i })
    await expect(input).toBeVisible({ timeout: 10_000 })

    await input.fill('upload')
    const option = page.getByRole('option', { name: /upload files/i })
    await expect(option).toBeVisible({ timeout: 10_000 })
    await option.click()

    await expect(page).toHaveURL('/upload', { timeout: 10_000 })
  })

  test('keyboard selection with arrows and enter', async ({ page }) => {
    await page.goto('/upload')
    await expect(page.getByRole('heading', { name: /upload/i })).toBeVisible({ timeout: 10_000 })

    await page.keyboard.press('ControlOrMeta+k')
    const input = page.getByRole('combobox', { name: /search commands/i })
    await expect(input).toBeVisible({ timeout: 10_000 })

    await input.fill('start study')
    await expect(page.getByRole('option', { name: /start study session/i })).toBeVisible({
      timeout: 10_000,
    })
    await page.keyboard.press('Enter')

    await expect(page).toHaveURL(/\/study/, { timeout: 10_000 })
  })
})
