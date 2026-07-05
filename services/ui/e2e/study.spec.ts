import { test, expect } from './fixtures'

test.describe('Study Hub', () => {
  test('study page loads with tabs', async ({ page }) => {
    await page.goto('/study')

    // Should show the 5 tabs: Plan, Flashcards, Timed, Exams, History
    await expect(page.getByRole('tab', { name: /plan/i })).toBeVisible({ timeout: 10_000 })
    await expect(page.getByRole('tab', { name: /flashcards/i })).toBeVisible()
    await expect(page.getByRole('tab', { name: /timed/i })).toBeVisible()
    await expect(page.getByRole('tab', { name: /exams/i })).toBeVisible()
    await expect(page.getByRole('tab', { name: /history/i })).toBeVisible()
  })

  test('plan tab is default', async ({ page }) => {
    await page.goto('/study')

    const planTab = page.getByRole('tab', { name: /plan/i })
    await expect(planTab).toBeVisible({ timeout: 10_000 })
    await expect(planTab).toHaveAttribute('data-state', 'active')
  })

  test('flashcards tab can be selected via URL param', async ({ page }) => {
    await page.goto('/study?tab=flashcards')

    const flashcardsTab = page.getByRole('tab', { name: /flashcards/i })
    await expect(flashcardsTab).toBeVisible({ timeout: 10_000 })
    await expect(flashcardsTab).toHaveAttribute('data-state', 'active')
  })

  test('exams tab can be navigated to via URL param', async ({ page }) => {
    await page.goto('/study?tab=exams')

    const examsTab = page.getByRole('tab', { name: /exams/i })
    await expect(examsTab).toBeVisible({ timeout: 10_000 })
    await expect(examsTab).toHaveAttribute('data-state', 'active')
  })
})
