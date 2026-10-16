import type { BrowserContext, Page, Request, Response } from '@playwright/test'
import {
  test,
  expect,
  testEmail,
  seedSession,
  seedLearner,
  openSession,
  closeSession,
} from './fixtures'

// M34 (M34-QA-015): thumbs up/down on AI flashcards and quiz questions inside
// the study runners (api.ai_feedback v1). Every test owns a user whose course is
// seeded with seedLearner (two cards, three questions), so a vote, a review or an
// archive never touches another test's rows. Each context stays under six full
// page loads (see service-worker.spec.ts).

const API_URL = process.env.E2E_API_URL || 'http://localhost:8000'
const PASSWORD = 'TestPass123!'

function newCode(): string {
  return `QAS${Math.random().toString(36).slice(2, 8).toUpperCase()}`
}

async function learner(browser: import('@playwright/test').Browser, opts = {}) {
  const email = testEmail()
  const code = newCode()
  const state = seedSession(email, PASSWORD)
  seedLearner(email, code)
  const context = await openSession(browser, state, opts)
  return { context, code }
}

const isVotePut = (x: Request) => x.url().endsWith('/api/feedback') && x.method() === 'PUT'
const isVoteDelete = (x: Request) => /\/api\/feedback\/[a-z_]+\/[^/]+$/.test(x.url()) && x.method() === 'DELETE'
const isReview = (x: Request) => x.url().endsWith('/api/study/review')

const cardFace = (page: Page) => page.locator('button[aria-label^="Showing"]')
const helpful = (page: Page) => page.getByRole('button', { name: 'Helpful', exact: true })
const notHelpful = (page: Page) => page.getByRole('button', { name: 'Not helpful', exact: true })

async function startFlashcards(page: Page, code: string): Promise<void> {
  await page.goto(`/study?tab=flashcards&course=${code}`)
  await expect(page.getByText('2 cards due for review')).toBeVisible({ timeout: 15_000 })
  await page.getByRole('button', { name: 'Start Session' }).click()
  await expect(page.getByText('Card 1 of 2')).toBeVisible()
}

async function noHorizontalScroll(page: Page): Promise<void> {
  const m = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    inner: window.innerWidth,
  }))
  expect(m.scroll).toBeLessThanOrEqual(m.inner)
}

test.describe('Flashcard study: rating the card itself', () => {
  test('thumbs up, then down with a reason, and the vote survives a reload', async ({ browser }) => {
    const { context, code } = await learner(browser)
    const page = await context.newPage()
    await startFlashcards(page, code)
    const front = (await cardFace(page).innerText()).trim()

    // Thumbs up sends a flashcard vote for the card on screen.
    const up = page.waitForRequest(isVotePut)
    await helpful(page).click()
    const upBody = (await up).postDataJSON()
    expect(upBody).toMatchObject({ target_type: 'flashcard', rating: 1 })
    await expect(helpful(page)).toHaveAttribute('aria-pressed', 'true')

    // Thumbs down asks why; the reason and comment travel with the vote.
    await notHelpful(page).click()
    await expect(page.getByRole('group', { name: "What wasn't right?" })).toBeVisible()
    await page.getByText('Inaccurate', { exact: true }).click()
    await page.getByLabel('Comment (optional)').fill('the date is wrong')
    const down = page.waitForRequest(isVotePut)
    await page.getByRole('button', { name: 'Send feedback' }).click()
    const downBody = (await down).postDataJSON()
    expect(downBody).toEqual({
      target_type: 'flashcard',
      target_id: upBody.target_id,
      rating: -1,
      reason: 'inaccurate',
      comment: 'the date is wrong',
    })
    await expect(notHelpful(page)).toHaveAttribute('aria-pressed', 'true')
    await expect(helpful(page)).toHaveAttribute('aria-pressed', 'false')

    // The server stored it.
    const mine = await context.request.get(
      `${API_URL}/api/feedback/mine?target_type=flashcard&target_ids=${upBody.target_id}`,
    )
    expect((await mine.json()).items).toEqual([
      expect.objectContaining({ target_id: upBody.target_id, rating: -1, reason: 'inaccurate' }),
    ])

    // After a reload the same card still carries the vote.
    await startFlashcards(page, code)
    for (let seen = 0; seen < 2; seen++) {
      if ((await cardFace(page).innerText()).trim() === front) break
      await cardFace(page).click()
      await page.getByRole('button', { name: /^Good/ }).click()
    }
    expect((await cardFace(page).innerText()).trim()).toBe(front)
    await expect(notHelpful(page)).toHaveAttribute('aria-pressed', 'true')
    await expect(helpful(page)).toHaveAttribute('aria-pressed', 'false')
    await closeSession(context)
  })

  test('Enter on a thumb does not flip the card and typing in the reason box does not rate it', async ({
    browser,
  }) => {
    const { context, code } = await learner(browser)
    const page = await context.newPage()
    await startFlashcards(page, code)
    const reviews: string[] = []
    page.on('request', (r) => {
      if (isReview(r)) reviews.push(r.postData() ?? '')
    })
    const showingQuestion = cardFace(page)
    await expect(showingQuestion).toHaveAttribute('aria-label', /Showing question/)

    // Enter on the thumb activates the thumb (opens the reason picker), not the card.
    await notHelpful(page).focus()
    await page.keyboard.press('Enter')
    await expect(page.getByRole('group', { name: "What wasn't right?" })).toBeVisible()
    await expect(showingQuestion).toHaveAttribute('aria-label', /Showing question/)

    // Space and Enter typed into the comment must not reveal the answer either.
    const comment = page.getByLabel('Comment (optional)')
    await comment.focus()
    await page.keyboard.type('not in the slides')
    await page.keyboard.press('Enter')
    await expect(comment).toHaveValue(/not in the slides/)
    await expect(showingQuestion).toHaveAttribute('aria-label', /Showing question/)

    // With the answer showing, digits typed in the comment are text, not a rating.
    await showingQuestion.click()
    await expect(showingQuestion).toHaveAttribute('aria-label', /Showing answer/)
    await comment.focus()
    await page.keyboard.type('1234')
    await expect(comment).toHaveValue(/1234$/)
    await expect(page.getByText('Card 1 of 2')).toBeVisible()
    expect(reviews).toEqual([])

    // Off the control the shortcuts still work: 3 is "Good" and rates the card.
    await page.getByRole('button', { name: 'Cancel' }).click()
    await page.locator('main').click({ position: { x: 4, y: 4 } })
    const review = page.waitForRequest(isReview)
    await page.keyboard.press('3')
    expect((await review).postDataJSON()).toMatchObject({ quality: 3 })
    await closeSession(context)
  })

  // PRODUCT BUG (found writing M34-QA-015; not from M34), pinned as an expected failure.
  // useRecordReview invalidates ['study', 'due', ...] on success, so the list the runner
  // walks shrinks by the card just rated while currentIndex still advances by one: with
  // two cards due, rating the first lands on "All caught up!" with the second never shown
  // (with twenty, every other card is skipped). `test.fail()` turns red the day it is
  // fixed; delete the annotation then.
  test('rating the first of two due cards shows the second', async ({ browser }) => {
    test.fail(true, 'the due list refetches without the rated card and the index skips past the next one')
    const { context, code } = await learner(browser)
    const page = await context.newPage()
    await startFlashcards(page, code)
    const first = (await cardFace(page).innerText()).trim()
    await cardFace(page).click()
    await page.getByRole('button', { name: /^Good/ }).click()
    // The other card should come up; waiting for it also waits out the due-list refetch.
    const other = first.includes('front 1') ? 'Learner front 2' : 'Learner front 1'
    await expect(cardFace(page).filter({ hasText: other })).toBeVisible()
    await expect(page.getByText('All caught up!')).toHaveCount(0)
    await closeSession(context)
  })

  test('at 375px the thumbs are 44px targets and the reason picker fits', async ({ browser }) => {
    const { context, code } = await learner(browser, { viewport: { width: 375, height: 667 } })
    const page = await context.newPage()
    await startFlashcards(page, code)
    for (const thumb of [helpful(page), notHelpful(page)]) {
      const box = (await thumb.boundingBox())!
      expect(box.height).toBeGreaterThanOrEqual(44)
      expect(box.width).toBeGreaterThanOrEqual(44)
    }
    await notHelpful(page).click()
    await expect(page.getByRole('group', { name: "What wasn't right?" })).toBeVisible()
    await noHorizontalScroll(page)
    for (const control of [
      page.getByRole('button', { name: 'Send feedback' }),
      page.getByRole('button', { name: 'Cancel' }),
      page.getByText('Unclear', { exact: true }),
    ]) {
      expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44)
    }
    await closeSession(context)
  })
})

test.describe('Timed session: rating cards and questions', () => {
  async function startTimed(context: BrowserContext, code: string): Promise<Page> {
    const page = await context.newPage()
    await page.goto('/study?tab=timed')
    await page.getByLabel('Course (optional)').fill(code)
    await page.getByRole('button', { name: /^Start \d+-minute session/ }).click()
    await expect(page.getByText('Flashcard', { exact: true })).toBeVisible({ timeout: 15_000 })
    return page
  }

  const rateCard = async (page: Page) => {
    await page.locator('button', { hasText: 'Click or press Space to reveal' }).click()
    await page.getByRole('button', { name: '4', exact: true }).click()
  }

  async function answerQuiz(page: Page) {
    await page.getByRole('button', { name: 'B. Beta' }).click()
    await page.getByRole('button', { name: 'Submit answer' }).click()
  }

  test('a card sends flashcard and a question sends quiz_question', async ({ browser }) => {
    const { context, code } = await learner(browser)
    const page = await startTimed(context, code)

    const cardVote = page.waitForRequest(isVotePut)
    await helpful(page).click()
    expect((await cardVote).postDataJSON()).toMatchObject({ target_type: 'flashcard', rating: 1 })
    await expect(helpful(page)).toHaveAttribute('aria-pressed', 'true')

    await rateCard(page)
    await rateCard(page)
    await expect(page.getByText('Quiz — Multiple Choice')).toBeVisible()
    const quizVote = page.waitForRequest(isVotePut)
    await helpful(page).click()
    expect((await quizVote).postDataJSON()).toMatchObject({ target_type: 'quiz_question', rating: 1 })
    await expect(helpful(page)).toHaveAttribute('aria-pressed', 'true')

    // A thumbs down on the question carries its reason.
    await notHelpful(page).click()
    await page.getByText('Unclear', { exact: true }).click()
    const down = page.waitForRequest(isVotePut)
    await page.getByRole('button', { name: 'Send feedback' }).click()
    expect((await down).postDataJSON()).toMatchObject({
      target_type: 'quiz_question',
      rating: -1,
      reason: 'unclear',
    })
    await closeSession(context)
  })

  test('voting on an item archived since it was shown says so and the session carries on', async ({
    browser,
  }) => {
    const { context, code } = await learner(browser)
    const page = await startTimed(context, code)
    const errors: string[] = []
    page.on('pageerror', (e) => errors.push(e.message))

    await rateCard(page)
    await rateCard(page)
    await expect(page.getByText('Quiz — Multiple Choice')).toBeVisible()

    // Archive the question on screen behind the page's back (the real delete route archives).
    const shown = (await page.getByText(/^Learner question \d/).first().innerText()).trim()
    const all = (await (await context.request.get(`${API_URL}/api/assets/quiz?course_code=${code}`)).json()) as {
      id: string
      question: string
    }[]
    const target = all.find((q) => q.question === shown)
    expect(target, `question "${shown}" in the course`).toBeTruthy()
    const archived = await context.request.delete(`${API_URL}/api/assets/quiz/${target!.id}`)
    expect(archived.ok()).toBeTruthy()

    const put = page.waitForResponse((r: Response) => isVotePut(r.request()))
    await helpful(page).click()
    expect((await put).status()).toBe(404)
    await expect(page.getByText('This item was archived, so it can no longer be rated.')).toBeVisible()
    // Not recorded as a vote, no crash, and the question can still be answered.
    await expect(helpful(page)).toHaveAttribute('aria-pressed', 'false')
    await expect(page.getByText(shown)).toBeVisible()
    await answerQuiz(page)
    await expect(page.getByRole('button', { name: 'Next' })).toBeVisible()
    expect(errors).toEqual([])
    await closeSession(context)
  })

  test('removing a vote clears it on the server', async ({ browser }) => {
    const { context, code } = await learner(browser)
    const page = await startTimed(context, code)
    const put = page.waitForRequest(isVotePut)
    await helpful(page).click()
    const id = (await put).postDataJSON().target_id
    await expect(helpful(page)).toHaveAttribute('aria-pressed', 'true')
    const del = page.waitForRequest(isVoteDelete)
    await helpful(page).click()
    expect((await del).url()).toContain(`/api/feedback/flashcard/${id}`)
    await expect(helpful(page)).toHaveAttribute('aria-pressed', 'false')
    const mine = await context.request.get(`${API_URL}/api/feedback/mine?target_type=flashcard&target_ids=${id}`)
    expect((await mine.json()).items).toEqual([])
    await closeSession(context)
  })
})
