import type { Page, Route } from '@playwright/test'
import { test, expect, seedWeakSpotCourse, deleteCourse } from './fixtures'

// M33 weak-spot engine in the browser: Study tonight card, mastery map, check-in,
// targeted practice and its daily cap. CI has no Celery worker, so the targeted
// generation endpoints are answered at the network layer; every other call (plan,
// heatmap, diagnostic, plan refresh) is the real API against seeded rows. Runs as
// the self-hosted default user, so there is no login (and no register budget spent).

const code = 'E2EWS'
const TARGETED = /\/api\/weak-spots\/targeted(\/[^/?]+)?(\?.*)?$/

test.describe.configure({ mode: 'serial' })
// The PWA service worker answers GETs itself, and page.route cannot see a request the
// worker makes: without this the polling GET reaches the real API and 404s.
test.use({ serviceWorkers: 'block' })

test.describe('Weak-spot engine', () => {
  test.beforeAll(async ({ playwright }) => {
    seedWeakSpotCourse(code)
    // The plan is frozen on its first read of the day, which an earlier spec may
    // have made before this course existed: rebuild it from the seeded evidence.
    const request = await playwright.request.newContext({
      baseURL: process.env.E2E_API_URL || 'http://localhost:8000',
    })
    const resp = await request.post('/api/study-plan/tonight/refresh', { data: {} })
    expect(resp.ok()).toBeTruthy()
    await request.dispose()
  })

  test.afterAll(async ({ playwright }) => {
    const request = await playwright.request.newContext()
    await deleteCourse(request, code)
    await request.dispose()
  })

  async function openMastery(page: Page) {
    await page.goto('/study?tab=mastery')
    const grid = page.getByRole('grid', { name: /mastery by course and week/i })
    await expect(grid).toBeVisible({ timeout: 10_000 })
    return grid
  }

  const cell = (page: Page, week: number) =>
    page.getByRole('button', { name: new RegExp(`^${code} week ${week}:`) })

  test('dashboard shows the Study tonight card with the seeded focus week', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText('Study tonight', { exact: true }).first()).toBeVisible({
      timeout: 10_000,
    })
    await expect(page.getByText('Focus weeks')).toBeVisible({ timeout: 10_000 })
    await expect(page.getByText(code).first()).toBeVisible()
    await expect(page.getByRole('button', { name: 'Start', exact: true })).toBeEnabled()
    await expect(page.getByRole('button', { name: /refresh plan/i })).toBeVisible()
  })

  test('mastery map renders and an unknown week is neutral, not red', async ({ page }) => {
    await openMastery(page)

    await expect(cell(page, 1)).toHaveAttribute('data-state', 'weak')
    await expect(cell(page, 1)).toHaveClass(/red/)
    await expect(cell(page, 2)).toHaveAttribute('data-state', 'solid')
    const unknown = cell(page, 3)
    await expect(unknown).toHaveAttribute('data-state', 'unknown')
    await expect(unknown).not.toHaveClass(/red/)
    await expect(unknown).toHaveAccessibleName(/not enough data/i)
  })

  test('check-in on an unknown week opens the timed runner', async ({ page }) => {
    await openMastery(page)
    await cell(page, 3).click()

    await page.getByRole('button', { name: /start a short check-in/i }).click()

    await expect(page).toHaveURL(/tab=timed/, { timeout: 10_000 })
  })

  test('Practise this week: 202, then completed, offers to refresh tonight', async ({ page }) => {
    let polls = 0
    const gen = {
      id: 'e2e-gen-1',
      course_id: 'c',
      week: 1,
      kind: 'quiz',
      requested_count: 5,
      dropped_duplicate_count: 0,
      dropped_uncited_count: 0,
      error_code: null,
      created_at: new Date().toISOString(),
    }
    await page.route(TARGETED, async (route: Route) => {
      if (route.request().method() === 'POST') {
        return route.fulfill({
          status: 202,
          json: { ...gen, status: 'queued', created_count: 0, item_ids: [], completed_at: null },
        })
      }
      polls += 1
      const done = polls > 1
      return route.fulfill({
        json: {
          ...gen,
          status: done ? 'completed' : 'running',
          created_count: done ? 3 : 0,
          item_ids: done ? ['i1', 'i2', 'i3'] : [],
          completed_at: done ? new Date().toISOString() : null,
        },
      })
    })
    await openMastery(page)
    await cell(page, 1).click()

    await page.getByRole('button', { name: /practise this week: questions/i }).click()

    await expect(page.getByText(/generating practice from your weak spots/i)).toBeVisible()
    await expect(page.getByText(/3 new practice items are ready/i)).toBeVisible({ timeout: 20_000 })
    const offer = page.getByRole('button', { name: /refresh tonight's plan/i })
    await expect(offer).toBeVisible()

    // The refresh is the real endpoint.
    await offer.click()
    await expect(page.getByText(/tonight's plan is updated/i)).toBeVisible({ timeout: 10_000 })
  })

  test('the daily cap (429) shows when the limit resets', async ({ page }) => {
    await page.route(TARGETED, (route: Route) =>
      route.fulfill({
        status: 429,
        headers: { 'Retry-After': '3600' },
        json: {
          detail: 'daily cap',
          code: 'targeted_daily_cap',
          limit: 6,
          reset_at: new Date(Date.now() + 3_600_000).toISOString(),
        },
      }),
    )
    await openMastery(page)
    await cell(page, 1).click()

    await page.getByRole('button', { name: /practise this week: flashcards/i }).click()

    const alert = page.getByRole('alert').filter({ hasText: /used today's practice generations/i })
    await expect(alert).toBeVisible({ timeout: 10_000 })
    await expect(alert).toContainText(/after \d{1,2}[:.]\d{2}/)
    await expect(alert).toContainText(/00:00 UTC/)
  })

  test.describe('at 375px', () => {
    test.use({ viewport: { width: 375, height: 667 } })

    for (const route of ['/', '/study?tab=mastery']) {
      test(`no horizontal scroll on ${route}`, async ({ page }) => {
        await page.goto(route)
        if (route === '/') {
          await expect(page.getByText('Study tonight', { exact: true }).first()).toBeVisible({
            timeout: 10_000,
          })
        } else {
          await cell(page, 1).click()
          await expect(
            page.getByRole('heading', { name: new RegExp(`${code} · Week 1`) }),
          ).toBeVisible({ timeout: 10_000 })
        }
        const m = await page.evaluate(() => ({
          scroll: document.documentElement.scrollWidth,
          inner: window.innerWidth,
        }))
        expect(m.scroll).toBeLessThanOrEqual(m.inner)
      })
    }
  })
})
