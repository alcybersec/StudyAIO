import { test, expect, testEmail, seedSession, openSession, closeSession } from './fixtures'

// PRODUCT BUG (found writing M34-QA-015), pinned as an expected failure.
//
// The service worker's general API route (src/sw.ts, NetworkFirst for every GET
// under /api/ except auth and the two study writes) also matches
// /api/uploads/pipeline-events, the long-lived SSE stream every page opens. The
// worker's own fetch for it does not end when the page that asked goes away, so
// each full page load leaves one stream open. After about six loads in one
// browser profile the HTTP/1.1 connection pool is full and every later request
// (the dashboard, a mutation, anything) waits forever. Measured against the CI
// stack: connections to the API grew by one or two per reload, the sixth reload
// never rendered, and the same run with serviceWorkers: 'block' stayed flat.
//
// `test.fail()` keeps the suite green while the bug stands and turns red the day
// it is fixed (exclude the stream from the route), which is the cue to delete
// the annotation. Other specs keep their own loads per context under six.

test('many full page loads in one browser profile keep rendering', async ({ browser }) => {
  test.fail(true, 'service worker NetworkFirst route captures the pipeline-events SSE stream')
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
