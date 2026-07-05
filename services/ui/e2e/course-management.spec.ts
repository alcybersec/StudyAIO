import { test, expect } from './fixtures'

const API_URL = process.env.E2E_API_URL || 'http://localhost:8000'

test.describe('Course management', () => {
  test('manage menu opens and delete modal gates the danger button', async ({ page }) => {
    const resp = await page.request.get(`${API_URL}/api/courses`)
    const courses = await resp.json()
    if (!Array.isArray(courses) || courses.length === 0) {
      test.skip()
      return
    }

    const courseCode: string = courses[0].code
    await page.goto(`/courses/${courseCode}`)
    await page.waitForLoadState('networkidle')

    // Open the manage menu
    const manageButton = page.getByRole('button', { name: /manage course/i })
    await expect(manageButton).toBeVisible({ timeout: 10_000 })
    await manageButton.click()

    // Menu items render
    await expect(page.getByRole('menuitem', { name: /rename course/i })).toBeVisible()
    await expect(page.getByRole('menuitem', { name: /archive course/i })).toBeVisible()

    // Open the delete confirmation modal
    await page.getByRole('menuitem', { name: /delete course/i }).click()
    await expect(page.getByText(new RegExp(`delete\\s+${courseCode}`, 'i'))).toBeVisible({
      timeout: 10_000,
    })

    // Danger button is disabled until the course code is typed
    const deleteButton = page.getByRole('button', { name: /delete permanently/i })
    await expect(deleteButton).toBeVisible()
    await expect(deleteButton).toBeDisabled()

    const confirmInput = page.locator('#delete-course-confirm')
    await confirmInput.fill('WRONG')
    await expect(deleteButton).toBeDisabled()

    await confirmInput.fill(courseCode)
    await expect(deleteButton).toBeEnabled()

    // Don't actually delete — close the modal
    await page.getByRole('button', { name: /cancel/i }).click()
    await expect(deleteButton).toBeHidden()
  })
})
