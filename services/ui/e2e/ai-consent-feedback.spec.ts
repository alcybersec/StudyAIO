import { test, expect, registerUser, loginViaAPI, giveAiConsent } from './fixtures'

const API_URL = process.env.E2E_API_URL || 'http://localhost:8000'

// API-level journeys for M33 S1. The CI stack runs in single-user mode, where
// the consent gate is deliberately off (the operator is treated as consented),
// so the 403 itself is covered by the integration tier; here we pin the wire
// shapes the SPA depends on.
test.describe('AI consent, AI feedback and usage events', () => {
  test('consent can be recorded and /auth/me reports the flag', async ({ page }) => {
    const { email, password } = await registerUser(page)
    await loginViaAPI(page, email, password)
    await giveAiConsent(page)

    const me = await page.request.get(`${API_URL}/api/auth/me`)
    expect(me.ok()).toBeTruthy()
    const body = await me.json()
    expect(body.ai_consent_required).toBe(false)
  })

  test('a stale disclosure version is refused with 409', async ({ page }) => {
    const { email, password } = await registerUser(page)
    await loginViaAPI(page, email, password)
    const resp = await page.request.post(`${API_URL}/api/auth/consent`, {
      data: { version: 0 },
    })
    expect(resp.status()).toBe(409)
  })

  test('rating a target that is not yours is a 404', async ({ page }) => {
    const { email, password } = await registerUser(page)
    await loginViaAPI(page, email, password)
    await giveAiConsent(page)
    const resp = await page.request.put(`${API_URL}/api/feedback`, {
      data: { target_type: 'summary', target_id: 'does-not-exist', rating: 1 },
    })
    expect(resp.status()).toBe(404)
  })

  test('view events are accepted; anything else is rejected', async ({ page }) => {
    const { email, password } = await registerUser(page)
    await loginViaAPI(page, email, password)
    const ok = await page.request.post(`${API_URL}/api/usage-events`, {
      data: { event: 'summary_viewed' },
    })
    expect(ok.status()).toBe(204)
    const forged = await page.request.post(`${API_URL}/api/usage-events`, {
      data: { event: 'quiz_completed' },
    })
    expect(forged.status()).toBe(422)
  })

  test('the retention readout is admin only', async ({ page }) => {
    const { email, password } = await registerUser(page)
    await loginViaAPI(page, email, password)
    const resp = await page.request.get(`${API_URL}/api/admin/usage/retention`)
    expect([401, 403]).toContain(resp.status())
  })
})
