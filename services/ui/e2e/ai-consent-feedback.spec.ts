import { request as pwRequest, type APIRequestContext } from '@playwright/test'
import { test, expect, testEmail, seedUser, expectNotThrottled } from './fixtures'

const API_URL = process.env.E2E_API_URL || 'http://localhost:8000'

// API-level journeys for M33 S1. The CI stack runs in single-user mode, where
// the consent gate is deliberately off (the operator is treated as consented),
// so the 403 itself is covered by the integration tier; here we pin the wire
// shapes the SPA depends on.
//
// Auth budget: register is limited to 3/minute and login to 5/minute per
// client, shared with auth.spec.ts and admin.spec.ts. This file therefore
// registers nobody (the user is seeded straight into the database) and logs in
// exactly once, reusing that session for every test.
test.describe('AI consent, AI feedback and usage events', () => {
  test.describe.configure({ mode: 'serial' })

  let api: APIRequestContext

  test.beforeAll(async () => {
    const email = testEmail()
    const password = 'TestPass123!'
    seedUser(email, password)
    api = await pwRequest.newContext()
    const login = await api.post(`${API_URL}/api/auth/login`, { data: { email, password } })
    expectNotThrottled(login.status(), 'login')
    expect(login.ok()).toBeTruthy()
  })

  test.afterAll(async () => {
    await api.dispose()
  })

  test('consent can be recorded and /auth/me reports the flag', async () => {
    const consent = await api.post(`${API_URL}/api/auth/consent`)
    expect(consent.ok()).toBeTruthy()
    expect((await consent.json()).ai_consent_required).toBe(false)

    const me = await api.get(`${API_URL}/api/auth/me`)
    expect(me.ok()).toBeTruthy()
    expect((await me.json()).ai_consent_required).toBe(false)
  })

  test('a stale disclosure version is refused with 409', async () => {
    const resp = await api.post(`${API_URL}/api/auth/consent`, { data: { version: 0 } })
    expect(resp.status()).toBe(409)
  })

  test('rating a target that is not yours is a 404', async () => {
    const resp = await api.put(`${API_URL}/api/feedback`, {
      data: { target_type: 'summary', target_id: 'does-not-exist', rating: 1 },
    })
    expect(resp.status()).toBe(404)
  })

  test('view events are accepted; anything else is rejected', async () => {
    const ok = await api.post(`${API_URL}/api/usage-events`, {
      data: { event: 'summary_viewed' },
    })
    expect(ok.status()).toBe(204)
    const forged = await api.post(`${API_URL}/api/usage-events`, {
      data: { event: 'quiz_completed' },
    })
    expect(forged.status()).toBe(422)
  })

  test('the retention readout is admin only', async () => {
    const resp = await api.get(`${API_URL}/api/admin/usage/retention`)
    expect([401, 403]).toContain(resp.status())
  })
})
