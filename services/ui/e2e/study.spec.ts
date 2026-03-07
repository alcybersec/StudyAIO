import { test, expect } from './fixtures'

test.describe('Study Hub', () => {
  test('study page loads with tabs', async ({ page }) => {
    await page.goto('/study')
    await page.waitForLoadState('networkidle')

    // Should show the 4 tabs: Flashcards, Timed, Exams, History
    await expect(page.getByRole('tab', { name: /flashcards/i })).toBeVisible({ timeout: 10_000 })
    await expect(page.getByRole('tab', { name: /timed/i })).toBeVisible()
    await expect(page.getByRole('tab', { name: /exams/i })).toBeVisible()
    await expect(page.getByRole('tab', { name: /history/i })).toBeVisible()
  })

  test('flashcards tab is default', async ({ page }) => {
    await page.goto('/study')
    await page.waitForLoadState('networkidle')

    const flashcardsTab = page.getByRole('tab', { name: /flashcards/i })
    await expect(flashcardsTab).toBeVisible({ timeout: 10_000 })
    await expect(flashcardsTab).toHaveAttribute('data-state', 'active')
  })

  test('exams tab can be navigated to via URL param', async ({ page }) => {
    await page.goto('/study?tab=exams')
    await page.waitForLoadState('networkidle')

    const examsTab = page.getByRole('tab', { name: /exams/i })
    await expect(examsTab).toBeVisible({ timeout: 10_000 })
    await expect(examsTab).toHaveAttribute('data-state', 'active')
  })

  test('old /exams route redirects to study hub', async ({ page }) => {
    await page.goto('/exams')
    await expect(page).toHaveURL(/\/study\?tab=exams/, { timeout: 10_000 })
  })
})
