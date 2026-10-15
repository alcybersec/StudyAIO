import { test, expect, seedCourseRow, deleteCourse, settle } from './fixtures'

const courseCode = 'E2EMGT'

test.describe.configure({ mode: 'serial' })

test.describe('Course management', () => {
  test.beforeAll(() => {
    seedCourseRow(courseCode)
  })

  test.afterAll(async ({ playwright }) => {
    const request = await playwright.request.newContext()
    await deleteCourse(request, courseCode)
    await request.dispose()
  })

  test('manage menu opens and delete modal gates the danger button', async ({ page }) => {
    await page.goto(`/courses/${courseCode}`)
    await settle(page)

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
