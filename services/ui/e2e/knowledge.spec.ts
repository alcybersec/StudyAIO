import { test, expect, seedCourseRow, deleteCourse, settle } from './fixtures'

const courseCode = 'E2EKG'

test.describe.configure({ mode: 'serial' })

test.describe('Knowledge', () => {
  // The concept graph is fed by the AI extraction task, which CI does not run,
  // so the keyboard-navigation test seeds the concepts it navigates.
  test.beforeAll(() => {
    seedCourseRow(courseCode, 3)
  })

  test.afterAll(async ({ playwright }) => {
    const request = await playwright.request.newContext()
    await deleteCourse(request, courseCode)
    await request.dispose()
  })

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
    await settle(page)

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
    await settle(page)

    await page.getByRole('group', { name: /view/i }).getByRole('button', { name: /list/i }).click()

    const listbox = page.getByRole('listbox', { name: /concepts/i })
    await expect(listbox).toBeVisible({ timeout: 10_000 })

    const options = listbox.getByRole('option')
    // At least the three seeded concepts (a dev database may hold more)
    await expect.poll(() => options.count()).toBeGreaterThanOrEqual(3)

    await options.first().focus()
    await expect(options.first()).toBeFocused()
    await page.keyboard.press('ArrowDown')
    await expect(options.nth(1)).toBeFocused()
    await page.keyboard.press('ArrowUp')
    await expect(options.first()).toBeFocused()
  })
})
