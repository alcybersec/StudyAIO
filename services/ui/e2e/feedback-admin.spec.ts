import {
  test,
  expect,
  testEmail,
  seedSession,
  seedLearner,
  openSession,
  closeSession,
} from './fixtures'

// PRODUCT BUG (found writing M34-QA-015), pinned as an expected failure.
//
// GET /api/admin/ai-feedback answers `by_target_type` as {type: {up, down}}
// (e.g. {"flashcard": {"up": 3, "down": 3}}), but AiFeedbackPanel renders each
// value as a count (the unit test fixture is {summary: 3}), so the first time
// anyone has rated anything the whole /admin page falls to the error boundary
// ("This page hit a problem"; React error #31, object with keys {up, down}).
// With an empty table it renders, which is why admin.spec.ts passes: it must run
// before any vote exists, and this file's name sorts after it for that reason
// (a spec that rates something must never sort before admin.spec.ts).
//
// `test.fail()` keeps the suite green while the bug stands and turns red the day
// it is fixed; delete the annotation then.

const API_URL = process.env.E2E_API_URL || 'http://localhost:8000'

test('the admin page renders once someone has rated an AI item', async ({ browser }) => {
  test.fail(true, 'AiFeedbackPanel renders by_target_type values ({up, down}) as numbers')

  // Someone rates a flashcard.
  const email = testEmail()
  const code = `QAF${Math.random().toString(36).slice(2, 7).toUpperCase()}`
  const state = seedSession(email, 'TestPass123!')
  seedLearner(email, code)
  const rater = await openSession(browser, state)
  const cards = (await (await rater.request.get(`${API_URL}/api/assets/flashcards?course_code=${code}`)).json()) as {
    id: string
  }[]
  const vote = await rater.request.put(`${API_URL}/api/feedback`, {
    data: { target_type: 'flashcard', target_id: cards[0].id, rating: -1, reason: 'inaccurate' },
  })
  expect(vote.ok()).toBeTruthy()
  await closeSession(rater)

  // An admin opens the console.
  const admin = await openSession(browser, seedSession(testEmail(), 'AdminPass123!', { admin: true }))
  const page = await admin.newPage()
  await page.goto('/admin')
  await expect(page.getByRole('heading', { name: /admin/i })).toBeVisible({ timeout: 10_000 })
  await expect(page.getByText('This page hit a problem')).toHaveCount(0)
  await expect(page.getByText('By content')).toBeVisible()
  await closeSession(admin)
})
