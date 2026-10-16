import type { Browser, BrowserContext } from '@playwright/test'
import { test, expect, testEmail, seedSession, openSession, closeSession } from './fixtures'

// GL#46: a brand-new account sees a three-step checklist and call-to-action
// empty widgets instead of blank cards. The account is seeded straight into the
// database (registering spends the shared 3/minute budget) with minted cookies;
// every test gets its own browser context carrying that session.
//
// M34: the checklist is server state (GET/PATCH /api/onboarding), so hiding it
// is stored on the user, not in the browser. The test that hides it therefore
// owns a user of its own; the others share one that is never dismissed.
// The advancing steps, pinning and the legacy-key migration live in
// onboarding.spec.ts.

const API_URL = process.env.E2E_API_URL || 'http://localhost:8000'

const PDF = `%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj
trailer<</Size 4/Root 1 0 R>>
%%EOF`

test.describe('First run on an empty account', () => {
  test.describe.configure({ mode: 'serial' })

  let storageState: ReturnType<typeof seedSession>

  test.beforeAll(() => {
    // Minted from the database, not via /login: the login budget (5/min) is
    // shared by every spec file, and a retried beforeAll would spend it again.
    storageState = seedSession(testEmail(), 'TestPass123!')
  })

  const open = (
    browser: Browser,
    opts: { lang?: 'ru'; viewport?: { width: number; height: number } } = {},
  ): Promise<BrowserContext> => openSession(browser, storageState, opts)

  test('the dashboard offers the three steps with upload as the next action', async ({ browser }) => {
    const context = await open(browser)
    const page = await context.newPage()
    await page.goto('/')
    const checklist = page.getByRole('region', { name: 'Get started' })
    await expect(checklist).toBeVisible({ timeout: 15_000 })
    const steps = checklist.getByRole('listitem')
    await expect(steps).toHaveCount(3)
    await expect(steps.nth(0)).toContainText('Upload your first lecture')
    await expect(steps.nth(1)).toContainText('Read your first summary')
    await expect(steps.nth(2)).toContainText('Take a short check-in')
    // Only step 1 can be acted on; the others say what unlocks them.
    await expect(checklist.getByRole('link', { name: 'Upload a lecture' })).toHaveAttribute('href', '/upload')
    await expect(checklist.getByRole('link', { name: 'Open summary' })).toHaveCount(0)
    await expect(checklist.getByRole('button', { name: 'Start the check-in' })).toHaveCount(0)
    await expect(checklist.getByText('Ready a minute or two after your upload finishes.')).toBeVisible()
    await closeSession(context)
  })

  test('empty widgets carry a call to action', async ({ browser }) => {
    const context = await open(browser)
    const page = await context.newPage()
    await page.goto('/')
    await expect(page.getByRole('heading', { name: /home/i })).toBeVisible({ timeout: 15_000 })
    const main = page.locator('main')
    // Several widgets point an empty account at an upload, others at studying.
    await expect(main.getByRole('link', { name: 'Upload a lecture' }).nth(1)).toBeVisible({ timeout: 15_000 })
    for (const link of await main.getByRole('link', { name: 'Upload a lecture' }).all()) {
      await expect(link).toHaveAttribute('href', '/upload')
    }
    const study = main.getByRole('link', { name: 'Start studying' }).first()
    await expect(study).toBeVisible()
    await expect(study).toHaveAttribute('href', '/study')
    await closeSession(context)
  })

  test('hiding the checklist is stored on the server and sticks across a reload', async ({ browser }) => {
    // Its own user: the dismissal is the user's, so it would hide the checklist
    // from every later test that shares `storageState`.
    const own = seedSession(testEmail(), 'TestPass123!')
    const context = await openSession(browser, own)
    const page = await context.newPage()
    await page.goto('/')
    const checklist = page.getByRole('region', { name: 'Get started' })
    await expect(checklist).toBeVisible({ timeout: 15_000 })

    const patched = page.waitForRequest(
      (r) => r.url().endsWith('/api/onboarding') && r.method() === 'PATCH',
    )
    await checklist.getByRole('button', { name: 'Hide this checklist' }).click()
    expect((await patched).postDataJSON()).toEqual({ checklist: 'dismissed' })
    await expect(checklist).toBeHidden()

    // After a reload the server, not the browser, says it stays hidden.
    const [reloaded] = await Promise.all([
      page.waitForResponse((r) => r.url().endsWith('/api/onboarding') && r.request().method() === 'GET'),
      page.reload(),
    ])
    expect(await reloaded.json()).toMatchObject({ checklist: 'dismissed', visible: false })
    await expect(page.getByRole('heading', { name: /home/i })).toBeVisible({ timeout: 15_000 })
    await expect(page.getByRole('region', { name: 'Get started' })).toHaveCount(0)

    // Nothing about the checklist is kept in the browser any more.
    const keys = await page.evaluate(() =>
      Object.keys(window.localStorage).filter((k) => k.startsWith('studyaio_onboarding')),
    )
    expect(keys).toEqual([])
    await closeSession(context)
  })

  test('the checklist and its actions are translated', async ({ browser }) => {
    const context = await open(browser, { lang: 'ru' })
    const page = await context.newPage()
    await page.goto('/')
    const checklist = page.getByRole('region', { name: 'Начало работы' })
    await expect(checklist).toBeVisible({ timeout: 15_000 })
    await expect(checklist.getByText('Загрузите первую лекцию')).toBeVisible()
    await expect(checklist.getByRole('button', { name: 'Скрыть этот список' })).toBeVisible()
    await closeSession(context)
  })

  test('at 375px the checklist fits and Hide is a 44px target', async ({ browser }) => {
    const context = await open(browser, { viewport: { width: 375, height: 667 } })
    const page = await context.newPage()
    await page.goto('/')
    const checklist = page.getByRole('region', { name: 'Get started' })
    await expect(checklist).toBeVisible({ timeout: 15_000 })
    const m = await page.evaluate(() => ({
      scroll: document.documentElement.scrollWidth,
      inner: window.innerWidth,
    }))
    expect(m.scroll).toBeLessThanOrEqual(m.inner)
    const hide = await checklist.getByRole('button', { name: 'Hide this checklist' }).boundingBox()
    expect(hide!.height).toBeGreaterThanOrEqual(44)
    await closeSession(context)
  })

  test('after a first upload step 1 is done and the summary step says it is waiting', async ({ browser }) => {
    const context = await open(browser)
    const page = await context.newPage()
    // The account's own session uploads a lecture; no worker runs, so it stays in the pipeline.
    const code = `QAF${Math.random().toString(36).slice(2, 7).toUpperCase()}`
    const up = await context.request.post(`${API_URL}/api/uploads?course_code=${code}&week=1`, {
      multipart: { file: { name: 'first.pdf', mimeType: 'application/pdf', buffer: Buffer.from(PDF) } },
    })
    expect(up.status()).toBe(201)

    await page.goto('/')
    const checklist = page.getByRole('region', { name: 'Get started' })
    await expect(checklist).toBeVisible({ timeout: 15_000 })
    const steps = checklist.getByRole('listitem')
    await expect(steps.nth(0).getByRole('link', { name: 'Upload a lecture' })).toHaveCount(0)
    await expect(steps.nth(1).getByText('Ready a minute or two after your upload finishes.')).toBeVisible()
    await expect(steps.nth(2).getByRole('button', { name: 'Start the check-in' })).toHaveCount(0)
    await closeSession(context)
  })
})
