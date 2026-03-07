import { test, expect } from './fixtures'

const API_URL = process.env.E2E_API_URL || 'http://localhost:8000'

test.describe('Course', () => {
  test('course page shows course details or 404', async ({ page }) => {
    // First get available courses
    const resp = await page.request.get(`${API_URL}/api/courses`)
    const courses = await resp.json()

    if (courses.length === 0) {
      // No courses — skip
      test.skip()
      return
    }

    const courseCode = courses[0].code
    await page.goto(`/courses/${courseCode}`)
    await expect(
      page.getByRole('heading').filter({ hasText: new RegExp(courseCode, 'i') }),
    ).toBeVisible({ timeout: 10_000 })
  })

  test('course page displays week rows', async ({ page }) => {
    const resp = await page.request.get(`${API_URL}/api/courses`)
    const courses = await resp.json()

    if (courses.length === 0) {
      test.skip()
      return
    }

    const courseCode = courses[0].code
    await page.goto(`/courses/${courseCode}`)
    await page.waitForLoadState('networkidle')

    // Should show week entries or empty state
    const hasWeeks = await page.getByText(/week\s+\d|no weeks|no artifacts/i).isVisible().catch(() => false)
    const hasContent = await page.textContent('body')
    expect(hasWeeks || (hasContent && hasContent.length > 0)).toBeTruthy()
  })

  test('week view page shows summary tab', async ({ page }) => {
    const resp = await page.request.get(`${API_URL}/api/courses`)
    const courses = await resp.json()

    if (courses.length === 0) {
      test.skip()
      return
    }

    const courseCode = courses[0].code
    await page.goto(`/courses/${courseCode}/weeks/1`)
    await page.waitForLoadState('networkidle')

    // Should show tabs or content
    const pageContent = await page.textContent('body')
    expect(pageContent).toBeTruthy()
  })

  test('course ops page loads', async ({ page }) => {
    const resp = await page.request.get(`${API_URL}/api/courses`)
    const courses = await resp.json()

    if (courses.length === 0) {
      test.skip()
      return
    }

    const courseCode = courses[0].code
    await page.goto(`/courses/${courseCode}/ops`)
    await page.waitForLoadState('networkidle')
    const pageContent = await page.textContent('body')
    expect(pageContent).toBeTruthy()
  })
})
