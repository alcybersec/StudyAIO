import { test, expect } from './fixtures'

test.describe('Knowledge', () => {
  test('page loads with heading and view toggle', async ({ page }) => {
    await page.goto('/knowledge')
    await expect(page.getByRole('heading', { name: /knowledge/i })).toBeVisible({ timeout: 10_000 })

    const toggle = page.getByRole('group', { name: /view/i })
    await expect(toggle).toBeVisible({ timeout: 10_000 })
    await expect(toggle.getByRole('button', { name: /graph/i })).toBeVisible()
    await expect(toggle.getByRole('button', { name: /list/i })).toBeVisible()
  })

  test('graph/list toggle switches views', async ({ page }) => {
    await page.goto('/knowledge')
    await page.waitForLoadState('networkidle')

    const toggle = page.getByRole('group', { name: /view/i })
    const listButton = toggle.getByRole('button', { name: /list/i })
    const graphButton = toggle.getByRole('button', { name: /graph/i })

    await listButton.click()
    await expect(listButton).toHaveAttribute('aria-pressed', 'true')
    await expect(graphButton).toHaveAttribute('aria-pressed', 'false')

    await graphButton.click()
    await expect(graphButton).toHaveAttribute('aria-pressed', 'true')
  })

  test('list view supports keyboard navigation', async ({ page }) => {
    await page.goto('/knowledge')
    await page.waitForLoadState('networkidle')

    await page.getByRole('group', { name: /view/i }).getByRole('button', { name: /list/i }).click()

    const listbox = page.getByRole('listbox', { name: /concepts/i })
    const hasList = await listbox.isVisible().catch(() => false)
    if (!hasList) {
      // No concepts extracted in this environment — nothing to navigate
      test.skip()
      return
    }

    const options = listbox.getByRole('option')
    const count = await options.count()
    if (count < 2) {
      test.skip()
      return
    }

    await options.first().focus()
    await expect(options.first()).toBeFocused()
    await page.keyboard.press('ArrowDown')
    await expect(options.nth(1)).toBeFocused()
    await page.keyboard.press('ArrowUp')
    await expect(options.first()).toBeFocused()
  })
})
