import type { Browser, BrowserContext, Locator, Page, Request, Response } from '@playwright/test'
import {
  test,
  expect,
  testEmail,
  seedSession,
  seedLearner,
  openSession,
  closeSession,
} from './fixtures'

// M34 (M34-QA-015): the first-run checklist is server state. GET/PATCH
// /api/onboarding derive the steps from the caller's own rows and store one
// preference (auto / dismissed / pinned); the old per-browser localStorage key is
// migrated by a single PATCH and then removed.
//
// Every test owns a user (minted session, no login) because the preference and
// the derived steps belong to the user: nothing here may leak across tests. The
// CI job runs no worker, so what the pipeline would have produced (summary,
// cards, questions) is seeded with seedLearner after a real upload.

const API_URL = process.env.E2E_API_URL || 'http://localhost:8000'
const PASSWORD = 'TestPass123!'

const PDF = `%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj
trailer<</Size 4/Root 1 0 R>>
%%EOF`

type Step = 'done' | 'active' | 'locked'

function newCode(): string {
  return `QAO${Math.random().toString(36).slice(2, 8).toUpperCase()}`
}

/** Matches the request, or the response to it, for `method /api/onboarding`. */
const isOnboarding = (method: string) => (x: Request | Response) => {
  const req = 'request' in x ? x.request() : x
  return req.url().endsWith('/api/onboarding') && req.method() === method
}

const checklistOf = (page: Page): Locator => page.getByRole('region', { name: 'Get started' })

async function expectSteps(checklist: Locator, expected: [Step, Step, Step]): Promise<void> {
  const items = checklist.getByRole('listitem')
  await expect(items).toHaveCount(3)
  for (const [i, status] of expected.entries()) {
    await expect(items.nth(i)).toHaveAttribute('data-status', status)
  }
}

async function onboardingOf(context: BrowserContext) {
  const resp = await context.request.get(`${API_URL}/api/onboarding`)
  expect(resp.status()).toBe(200)
  return (await resp.json()) as {
    phase: string
    checklist: string
    visible: boolean
    steps: { upload: Step; summary: Step; check_in: Step }
    summary_target: { course_code: string; week: number } | null
  }
}

async function noHorizontalScroll(page: Page): Promise<void> {
  const m = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    inner: window.innerWidth,
  }))
  expect(m.scroll).toBeLessThanOrEqual(m.inner)
}

async function uploadFirstLecture(context: BrowserContext, code: string): Promise<void> {
  const up = await context.request.post(`${API_URL}/api/uploads?course_code=${code}&week=1`, {
    multipart: { file: { name: 'first.pdf', mimeType: 'application/pdf', buffer: Buffer.from(PDF) } },
  })
  expect(up.status()).toBe(201)
}

/** A user with a summary and questions, who has also answered one question: every step done. */
async function finishedUser(browser: Browser) {
  const email = testEmail()
  const state = seedSession(email, PASSWORD)
  const code = newCode()
  seedLearner(email, code)
  const context = await openSession(browser, state)
  const questions = await (await context.request.get(`${API_URL}/api/assets/quiz?course_code=${code}`)).json()
  expect(questions.length).toBeGreaterThan(0)
  const attempt = await context.request.post(`${API_URL}/api/study/quiz-attempt`, {
    data: { quiz_question_id: questions[0].id, selected_answer: 'B', is_correct: true },
  })
  expect(attempt.status()).toBe(201)
  return { context, code }
}

test.describe('Onboarding checklist is server state', () => {
  test('a new user sees the checklist and upload, summary and check-in advance it from /api/onboarding', async ({
    browser,
  }) => {
    const email = testEmail()
    const code = newCode()
    const state = seedSession(email, PASSWORD)
    const context = await openSession(browser, state)
    const page = await context.newPage()

    // New: step 1 is the only live one.
    const [first] = await Promise.all([page.waitForResponse(isOnboarding('GET')), page.goto('/')])
    expect(await first.json()).toMatchObject({
      phase: 'new',
      checklist: 'auto',
      visible: true,
      steps: { upload: 'active', summary: 'locked', check_in: 'locked' },
    })
    await expectSteps(checklistOf(page), ['active', 'locked', 'locked'])

    // Uploaded, still in the pipeline (no worker): step 1 done, the rest wait. A reload keeps it.
    await uploadFirstLecture(context, code)
    await page.reload()
    await expectSteps(checklistOf(page), ['done', 'locked', 'locked'])
    expect((await onboardingOf(context)).phase).toBe('processing')
    await page.reload()
    await expectSteps(checklistOf(page), ['done', 'locked', 'locked'])
    await closeSession(context)

    // The summary exists: reading it becomes the next step, the check-in is open too.
    // A fresh browser context for the rest: the state is the server's, and each full page
    // load in one context leaks a pipeline-event stream through the service worker (see
    // service-worker.spec.ts), so one context cannot carry every step on a 6-connection pool.
    seedLearner(email, code)
    const second = await openSession(browser, state)
    const page2 = await second.newPage()
    await page2.goto('/')
    const checklist = checklistOf(page2)
    await expectSteps(checklist, ['done', 'active', 'active'])
    const target = (await onboardingOf(second)).summary_target
    expect(target).toMatchObject({ course_code: code, week: 1 })
    await expect(checklist.getByRole('link', { name: 'Open summary' })).toHaveAttribute(
      'href',
      `/courses/${code}/weeks/1`,
    )

    // Reading it records a view, and the step is done on the next look.
    const viewed = page2.waitForResponse(
      (r) => r.url().endsWith('/api/usage-events') && r.request().postDataJSON()?.event === 'summary_viewed',
    )
    await checklist.getByRole('link', { name: 'Open summary' }).click()
    await expect(page2).toHaveURL(new RegExp(`/courses/${code}/weeks/1`))
    expect((await viewed).status()).toBe(204)
    await page2.goto('/')
    await expectSteps(checklistOf(page2), ['done', 'done', 'active'])
    expect((await onboardingOf(second)).steps).toEqual({ upload: 'done', summary: 'done', check_in: 'active' })

    // The check-in runs the week's questions; answering one finishes the last step.
    await checklistOf(page2).getByRole('button', { name: 'Start the check-in' }).click()
    await expect(page2).toHaveURL(/\/study\?tab=timed/, { timeout: 15_000 })
    await expect(page2.getByText('Learner question', { exact: false }).first()).toBeVisible({ timeout: 15_000 })
    await page2.getByRole('button', { name: 'B. Beta' }).click()
    const attempted = page2.waitForResponse((r) => r.url().endsWith('/api/study/quiz-attempt'))
    await page2.getByRole('button', { name: 'Submit answer' }).click()
    expect((await attempted).status()).toBe(201)

    const done = await onboardingOf(second)
    expect(done).toMatchObject({ phase: 'done', checklist: 'auto', visible: false })
    expect(done.steps).toEqual({ upload: 'done', summary: 'done', check_in: 'done' })
    await page2.goto('/')
    await expect(page2.getByRole('heading', { name: /home/i })).toBeVisible({ timeout: 15_000 })
    await expect(checklistOf(page2)).toHaveCount(0)
    await closeSession(second)
  })

  test('hiding sticks across a reload and in a second browser context, and Settings brings it back', async ({
    browser,
  }) => {
    const state = seedSession(testEmail(), PASSWORD)
    const first = await openSession(browser, state)
    const page = await first.newPage()
    await page.goto('/')
    await expect(checklistOf(page)).toBeVisible({ timeout: 15_000 })

    const patched = page.waitForRequest(isOnboarding('PATCH'))
    await checklistOf(page).getByRole('button', { name: 'Hide this checklist' }).click()
    expect((await patched).postDataJSON()).toEqual({ checklist: 'dismissed' })
    await expect(checklistOf(page)).toBeHidden()

    await page.reload()
    await expect(page.getByRole('heading', { name: /home/i })).toBeVisible({ timeout: 15_000 })
    await expect(checklistOf(page)).toHaveCount(0)

    // A different browser profile, same account: the server remembers, localStorage cannot.
    const second = await openSession(browser, state)
    const other = await second.newPage()
    const [got] = await Promise.all([other.waitForResponse(isOnboarding('GET')), other.goto('/')])
    expect(await got.json()).toMatchObject({ checklist: 'dismissed', visible: false })
    await expect(other.getByRole('heading', { name: /home/i })).toBeVisible({ timeout: 15_000 })
    await expect(checklistOf(other)).toHaveCount(0)

    // "Show checklist on Home" pins it; it returns on Home and stays across a reload.
    await other.goto('/settings')
    const pinned = other.waitForRequest(isOnboarding('PATCH'))
    await other.getByRole('button', { name: 'Show checklist on Home' }).click()
    expect((await pinned).postDataJSON()).toEqual({ checklist: 'pinned' })
    await expect(other.getByText('The checklist is back on your Home page.')).toBeVisible()
    await other.goto('/')
    await expect(checklistOf(other)).toBeVisible({ timeout: 15_000 })
    await other.reload()
    await expect(checklistOf(other)).toBeVisible({ timeout: 15_000 })
    expect(await onboardingOf(second)).toMatchObject({ checklist: 'pinned', visible: true })
    await closeSession(second)
    await closeSession(first)
  })

  test('pinned brings the checklist back even when every step is done', async ({ browser }) => {
    const { context } = await finishedUser(browser)
    expect(await onboardingOf(context)).toMatchObject({ phase: 'done', checklist: 'auto', visible: false })
    const page = await context.newPage()
    await page.goto('/')
    await expect(page.getByRole('heading', { name: /home/i })).toBeVisible({ timeout: 15_000 })
    await expect(checklistOf(page)).toHaveCount(0)

    await page.goto('/settings')
    const pinned = page.waitForRequest(isOnboarding('PATCH'))
    await page.getByRole('button', { name: 'Show checklist on Home' }).click()
    expect((await pinned).postDataJSON()).toEqual({ checklist: 'pinned' })
    await expect(page.getByText('The checklist is back on your Home page.')).toBeVisible()

    await page.goto('/')
    await expectSteps(checklistOf(page), ['done', 'done', 'done'])
    expect(await onboardingOf(context)).toMatchObject({ phase: 'done', checklist: 'pinned', visible: true })
    await page.reload()
    await expectSteps(checklistOf(page), ['done', 'done', 'done'])
    await closeSession(context)
  })

  test('a legacy localStorage dismissal is sent as one PATCH, the key is removed and no checklist shows', async ({
    browser,
  }) => {
    const context = await openSession(browser, seedSession(testEmail(), PASSWORD))
    const me = await (await context.request.get(`${API_URL}/api/auth/me`)).json()
    const key = `studyaio_onboarding:${me.id}`
    // Once per tab, not on every navigation: a re-seeded key would defeat the check below.
    await context.addInitScript(
      ([k]) => {
        if (!sessionStorage.getItem('e2e-legacy-seeded')) {
          sessionStorage.setItem('e2e-legacy-seeded', '1')
          localStorage.setItem(k, JSON.stringify({ dismissed: true }))
        }
      },
      [key],
    )
    const page = await context.newPage()
    const patches: unknown[] = []
    page.on('request', (r) => {
      if (isOnboarding('PATCH')(r)) patches.push(r.postDataJSON())
    })
    const [migrated] = await Promise.all([
      page.waitForResponse(isOnboarding('PATCH')),
      page.goto('/'),
    ])
    expect(await migrated.json()).toMatchObject({ checklist: 'dismissed', visible: false })
    await expect(page.getByRole('heading', { name: /home/i })).toBeVisible({ timeout: 15_000 })
    await expect(checklistOf(page)).toHaveCount(0)
    await expect.poll(() => page.evaluate((k) => localStorage.getItem(k), key)).toBeNull()
    expect(patches).toEqual([{ checklist: 'dismissed' }])

    // Migrated once: a reload asks the server and sends nothing.
    await page.reload()
    await expect(page.getByRole('heading', { name: /home/i })).toBeVisible({ timeout: 15_000 })
    await expect(checklistOf(page)).toHaveCount(0)
    expect(patches).toHaveLength(1)
    expect(await onboardingOf(context)).toMatchObject({ checklist: 'dismissed', visible: false })
    await closeSession(context)
  })

  test('a legacy key that is not a dismissal is cleared without a PATCH and the checklist stays', async ({
    browser,
  }) => {
    const context = await openSession(browser, seedSession(testEmail(), PASSWORD))
    const me = await (await context.request.get(`${API_URL}/api/auth/me`)).json()
    const key = `studyaio_onboarding:${me.id}`
    await context.addInitScript(
      ([k]) => {
        if (!sessionStorage.getItem('e2e-legacy-seeded')) {
          sessionStorage.setItem('e2e-legacy-seeded', '1')
          localStorage.setItem(k, JSON.stringify({ dismissed: false }))
        }
      },
      [key],
    )
    const page = await context.newPage()
    const patches: unknown[] = []
    page.on('request', (r) => {
      if (isOnboarding('PATCH')(r)) patches.push(r.postDataJSON())
    })
    await page.goto('/')
    await expect(checklistOf(page)).toBeVisible({ timeout: 15_000 })
    await expect.poll(() => page.evaluate((k) => localStorage.getItem(k), key)).toBeNull()
    expect(patches).toEqual([])
    await closeSession(context)
  })

  test('at 375px the checklist with every action, and the pin button, fit without horizontal scroll', async ({
    browser,
  }) => {
    const email = testEmail()
    const code = newCode()
    const state = seedSession(email, PASSWORD)
    seedLearner(email, code)
    const context = await openSession(browser, state, { viewport: { width: 375, height: 667 } })
    const page = await context.newPage()
    await page.goto('/')
    // A summary to read and a check-in to start: the busiest the card gets.
    const checklist = checklistOf(page)
    await expectSteps(checklist, ['done', 'active', 'active'])
    await expect(checklist.getByRole('link', { name: 'Open summary' })).toBeVisible()
    await expect(checklist.getByRole('button', { name: 'Start the check-in' })).toBeVisible()
    await noHorizontalScroll(page)
    for (const target of [
      checklist.getByRole('link', { name: 'Open summary' }),
      checklist.getByRole('button', { name: 'Start the check-in' }),
      checklist.getByRole('button', { name: 'Hide this checklist' }),
    ]) {
      expect((await target.boundingBox())!.height).toBeGreaterThanOrEqual(44)
    }

    await page.goto('/settings')
    const pin = page.getByRole('button', { name: 'Show checklist on Home' })
    await expect(pin).toBeVisible({ timeout: 15_000 })
    await noHorizontalScroll(page)
    await closeSession(context)
  })
})
