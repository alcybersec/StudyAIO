import { test, expect, deleteCourse, seedCourseRow } from './fixtures'
import type { Page } from '@playwright/test'

// GL#49 (explicit course and week on upload) and GL#47 (upload progress follows
// the user around the app). The CI stack runs no worker, so the pipeline never
// emits events by itself: the SSE stream is stubbed, and what is asserted is the
// SPA's handling of it plus what the real API stored.

const API_URL = process.env.E2E_API_URL || 'http://localhost:8000'

function newCode(): string {
  return `QAU${Math.random().toString(36).slice(2, 8).toUpperCase()}`
}

/** A parseable PDF whose bytes differ per call, so the per-user dedup never fires. */
function uniquePdf(name: string) {
  const body = `%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj
%% ${name} ${Date.now()} ${Math.random()}
trailer<</Size 4/Root 1 0 R>>
%%EOF`
  return { name, mimeType: 'application/pdf', buffer: Buffer.from(body) }
}

/**
 * Swap EventSource for a stand-in the test drives. Playwright cannot hold a
 * route open, and a fulfilled stream ends at once and makes the app reconnect,
 * so the page gets a fake connection instead; `emit` pushes a pipeline frame.
 */
async function stubPipelineEvents(page: Page) {
  await page.addInitScript(() => {
    type Listener = (e: { data: string }) => void
    class FakeEventSource {
      readyState = 1
      onopen: ((e: unknown) => void) | null = null
      onerror: ((e: unknown) => void) | null = null
      listeners: Record<string, Listener[]> = {}
      constructor(public url: string) {
        ;((window as unknown as { __es: FakeEventSource[] }).__es ||= []).push(this)
        setTimeout(() => this.onopen?.({}), 0)
      }
      addEventListener(type: string, fn: Listener) {
        ;(this.listeners[type] ||= []).push(fn)
      }
      removeEventListener() {}
      close() {
        this.readyState = 2
      }
    }
    ;(window as unknown as { EventSource: unknown }).EventSource = FakeEventSource
    ;(window as unknown as Record<string, unknown>).__emitPipeline = (data: unknown) => {
      for (const es of (window as unknown as { __es?: FakeEventSource[] }).__es ?? []) {
        if (es.readyState === 1) for (const fn of es.listeners.pipeline ?? []) fn({ data: JSON.stringify(data) })
      }
    }
  })
  return (artifactId: string, stage: string, status: string) =>
    page.evaluate(
      (d) => (window as unknown as { __emitPipeline: (x: unknown) => void }).__emitPipeline(d),
      { artifact_id: artifactId, stage, status, message: null },
    )
}

async function chooseManual(page: Page) {
  await page.getByRole('radio', { name: 'Choose course & week' }).check()
}

async function chooseCourse(page: Page, code: string) {
  await page.getByRole('button', { name: 'Course', exact: true }).click()
  await page.getByRole('menuitemradio', { name: new RegExp(`^${code}`) }).click()
}

/** The app-wide chip (a link with role=status) shown while uploads are processing. */
const chip = (page: Page) => page.getByRole('status').filter({ hasText: /file processing/ })
const dropZone = (page: Page) => page.getByRole('button', { name: /Drop lecture files here/ })
const stage = (page: Page, name: string, status: string) =>
  page.getByRole('listitem', { name: `${name}: ${status}` })

test.describe('Upload placement (course and week)', () => {
  let code: string

  test.beforeEach(async () => {
    code = newCode()
    seedCourseRow(code)
  })

  test.afterEach(async ({ request }) => {
    await deleteCourse(request, code)
  })

  test('the picker defaults to letting StudyAIO decide and hides the course fields', async ({ page }) => {
    await page.goto('/upload')
    await expect(page.getByRole('radio', { name: 'Let StudyAIO decide' })).toBeChecked({ timeout: 10_000 })
    await expect(page.getByRole('textbox', { name: 'Week' })).toBeHidden()
    await expect(dropZone(page)).toBeEnabled()
    await chooseManual(page)
    await expect(page.getByRole('textbox', { name: 'Week' })).toBeVisible()
    await expect(page.getByText('The file goes straight to extraction; classification is skipped.')).toBeVisible()
  })

  test('a course without a week keeps the drop zone disabled until the week is valid', async ({ page }) => {
    await page.goto('/upload')
    await chooseManual(page)
    await expect(dropZone(page)).toBeDisabled()
    await chooseCourse(page, code)
    await expect(dropZone(page)).toBeDisabled()
    await expect(page.getByText('Enter a week from 1 to 52')).toBeVisible()

    const week = page.getByRole('textbox', { name: 'Week' })
    for (const bad of ['0', '53', 'x', '3.5']) {
      await week.fill(bad)
      await expect(dropZone(page)).toBeDisabled()
    }
    await week.fill('3')
    await expect(dropZone(page)).toBeEnabled()
    await expect(page.getByText('Enter a week from 1 to 52')).toBeHidden()

    // Back to automatic placement: no course or week needed any more.
    await week.fill('')
    await expect(dropZone(page)).toBeDisabled()
    await page.getByRole('radio', { name: 'Let StudyAIO decide' }).check()
    await expect(dropZone(page)).toBeEnabled()
  })

  test('a placed upload lands in that course and week, and its rail starts at extract', async ({
    page,
    request,
  }) => {
    const emit = await stubPipelineEvents(page)
    await page.goto('/upload')
    await chooseManual(page)
    await chooseCourse(page, code)
    await page.getByRole('textbox', { name: 'Week' }).fill('3')

    const uploaded = page.waitForResponse(
      (r) => r.url().includes('/api/uploads') && r.request().method() === 'POST',
    )
    await page.locator('input[type="file"]').first().setInputFiles(uniquePdf('whatever-name.pdf'))
    const resp = await uploaded
    expect(resp.url()).toContain(`course_code=${code}`)
    expect(resp.url()).toContain('week=3')
    expect(resp.status()).toBe(201)
    const { artifact_id: artifactId } = await resp.json()

    // Classification is skipped: ingest and classify are already satisfied, extract is next.
    await expect(page.getByText('whatever-name.pdf')).toBeVisible()
    await expect(stage(page, 'ingest', 'done')).toBeVisible()
    await expect(stage(page, 'classify', 'done')).toBeVisible()
    await expect(stage(page, 'extract', 'pending')).toBeVisible()
    await expect(stage(page, 'summarize', 'pending')).toBeVisible()

    // The server agrees: the artifact is in the chosen course and week, with no review to answer.
    const week = await (await request.get(`${API_URL}/api/courses/${code}/weeks/3`)).json()
    const artifact = week.artifacts.find((a: { id: string }) => a.id === artifactId)
    expect(artifact).toBeTruthy()
    expect(artifact.status).toBe('classified')
    const reviews = await (await request.get(`${API_URL}/api/review-items`)).json()
    expect(reviews.filter((r: { entity_id: string }) => r.entity_id === artifactId)).toHaveLength(0)

    // When the worker reports extract running, the rail follows from there.
    await emit(artifactId, 'extract', 'started')
    await expect(stage(page, 'extract', 'running')).toBeVisible({ timeout: 15_000 })
    await expect(stage(page, 'ingest', 'done')).toBeVisible()
  })

  test('progress survives leaving the Upload page, with a global chip while it runs', async ({ page }) => {
    const emit = await stubPipelineEvents(page)
    await page.goto('/upload')
    await chooseManual(page)
    await chooseCourse(page, code)
    await page.getByRole('textbox', { name: 'Week' }).fill('2')
    const uploaded = page.waitForResponse(
      (r) => r.url().includes('/api/uploads') && r.request().method() === 'POST',
    )
    await page.locator('input[type="file"]').first().setInputFiles(uniquePdf('persist-me.pdf'))
    const artifactId = (await (await uploaded).json()).artifact_id
    await emit(artifactId, 'extract', 'started')
    await expect(stage(page, 'extract', 'running')).toBeVisible({ timeout: 15_000 })
    // On the Upload page the chip stays out of the way.
    await expect(chip(page)).toBeHidden()

    // Navigate inside the SPA (no reload): Home, then back.
    await page.locator('aside').getByRole('link', { name: 'Home', exact: true }).click()
    await expect(page).toHaveURL('/')
    await expect(chip(page)).toBeVisible()

    await page.locator('aside a[href="/upload"]').click()
    await expect(page).toHaveURL('/upload')
    await expect(page.getByText('persist-me.pdf')).toBeVisible()
    await expect(stage(page, 'extract', 'running')).toBeVisible()
    await expect(stage(page, 'ingest', 'done')).toBeVisible()
    await expect(chip(page)).toBeHidden()

    // The chip clears once the run reaches a terminal event.
    await emit(artifactId, 'assets', 'completed')
    await expect(stage(page, 'assets', 'done')).toBeVisible()
    await page.locator('aside').getByRole('link', { name: 'Home', exact: true }).click()
    await expect(page).toHaveURL('/')
    await expect(page.getByRole('heading', { name: /home/i })).toBeVisible()
    await expect(chip(page)).toBeHidden()
  })
})

test.describe('Upload placement in Russian', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => window.localStorage.setItem('studyaio-language', 'ru'))
  })

  test('the picker and its validation are translated', async ({ page }) => {
    await page.goto('/upload')
    await expect(page.getByRole('radio', { name: 'Пусть StudyAIO определит сам' })).toBeChecked({ timeout: 10_000 })
    await page.getByRole('radio', { name: 'Выбрать курс и неделю' }).check()
    await expect(page.getByText('Файл сразу идёт на извлечение; классификация пропускается.')).toBeVisible()
    await expect(page.getByText('Выберите курс или доверьтесь StudyAIO')).toBeVisible()
    await expect(page.getByText('Введите неделю от 1 до 52')).toBeVisible()
    await expect(page.getByRole('textbox', { name: 'Неделя' })).toBeVisible()
  })
})

test.describe('Upload placement at 375px', () => {
  test.use({ viewport: { width: 375, height: 667 } })

  test('the picker fits the screen and its controls are tappable', async ({ page }) => {
    await page.goto('/upload')
    await expect(page.getByRole('radio', { name: 'Let StudyAIO decide' })).toBeVisible({ timeout: 10_000 })
    await chooseManual(page)
    await expect(page.getByRole('textbox', { name: 'Week' })).toBeVisible()
    const m = await page.evaluate(() => ({
      scroll: document.documentElement.scrollWidth,
      inner: window.innerWidth,
    }))
    expect(m.scroll).toBeLessThanOrEqual(m.inner)
    for (const label of ['Let StudyAIO decide', 'Choose course & week']) {
      const box = await page.locator('label').filter({ hasText: label }).boundingBox()
      expect(box!.height).toBeGreaterThanOrEqual(44)
      expect(box!.x + box!.width).toBeLessThanOrEqual(375)
    }
  })
})
