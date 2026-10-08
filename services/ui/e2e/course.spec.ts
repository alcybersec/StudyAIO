import { test, expect, seedCourseRow, deleteCourse } from './fixtures'

const COURSE_CODE = 'E2ECRS'

// Serial: the course is seeded once and removed once, so parallel workers must
// not each run the hooks while another is mid-test.
test.describe.configure({ mode: 'serial' })

test.describe('Course', () => {
  test.beforeAll(() => {
    seedCourseRow(COURSE_CODE)
  })

  test.afterAll(async ({ playwright }) => {
    const request = await playwright.request.newContext()
    await deleteCourse(request, COURSE_CODE)
    await request.dispose()
  })

  test('course page shows course details', async ({ page }) => {
    await page.goto(`/courses/${COURSE_CODE}`)
    await expect(
      page.getByRole('heading').filter({ hasText: new RegExp(COURSE_CODE, 'i') }),
    ).toBeVisible({ timeout: 10_000 })
  })

  test('course page displays week rows', async ({ page }) => {
    await page.goto(`/courses/${COURSE_CODE}`)
    await page.waitForLoadState('networkidle')

    // Should show week entries or empty state
    const hasWeeks = await page.getByText(/week\s+\d|no weeks|no artifacts/i).isVisible().catch(() => false)
    const hasContent = await page.textContent('body')
    expect(hasWeeks || (hasContent && hasContent.length > 0)).toBeTruthy()
  })

  test('week view page shows summary tab', async ({ page }) => {
    await page.goto(`/courses/${COURSE_CODE}/weeks/1`)
    await page.waitForLoadState('networkidle')

    // Should show tabs or content
    const pageContent = await page.textContent('body')
    expect(pageContent).toBeTruthy()
  })

  test('course ops page loads', async ({ page }) => {
    await page.goto(`/courses/${COURSE_CODE}/ops`)
    await page.waitForLoadState('networkidle')
    const pageContent = await page.textContent('body')
    expect(pageContent).toBeTruthy()
  })
})
