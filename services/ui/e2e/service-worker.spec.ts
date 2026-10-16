import { test, expect, testEmail, seedSession, openSession, closeSession } from './fixtures'

// Regression guard: the service worker's general API route once captured the
// long-lived /api/uploads/pipeline-events SSE stream, so each full page load left
// a stream open and after about six loads in one profile the HTTP/1.1 connection
// pool was full and nothing rendered. The stream is now excluded from the route.

test('many full page loads in one browser profile keep rendering', async ({ browser }) => {
  test.setTimeout(60_000)
  const context = await openSession(browser, seedSession(testEmail(), 'TestPass123!'))
  const page = await context.newPage()
  await page.goto('/')
  await expect(page.getByRole('region', { name: 'Get started' })).toBeVisible({ timeout: 15_000 })
  try {
    for (let i = 0; i < 9; i++) {
      await page.reload()
      await expect(page.getByRole('region', { name: 'Get started' })).toBeVisible({ timeout: 6_000 })
    }
  } finally {
    await closeSession(context)
  }
})
