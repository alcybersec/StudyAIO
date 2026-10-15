import { test, expect, testEmail, loginViaAPI, seedDb, settle } from './fixtures'

const API_URL = process.env.E2E_API_URL || 'http://localhost:8000'

test.describe('Admin', () => {
  test('admin API is role-gated', async ({ page }) => {
    // A fresh context carries no cookie, so it has no admin session.
    const resp = await page.request.get(`${API_URL}/api/admin/metrics`)
    // Without an authenticated admin the endpoint must reject the request
    expect([401, 403]).toContain(resp.status())
  })

  test('admin page renders metrics and user table for admins', async ({ page }) => {
    // An admin session: no API grants the first admin, so seed one with a
    // password, then log in through the public API. A self-hosted stack serves
    // the cookie's identity ahead of the default user.
    const email = testEmail()
    const password = 'AdminPass123!'
    seedDb('admin', email, password)
    await loginViaAPI(page, email, password)
    const resp = await page.request.get(`${API_URL}/api/admin/metrics`)
    expect(resp.ok()).toBeTruthy()

    await page.goto('/admin')
    await expect(page.getByRole('heading', { name: /admin/i })).toBeVisible({ timeout: 10_000 })
    await settle(page)

    // Metrics cards
    await expect(page.getByText(/^users$/i).first()).toBeVisible()
    await expect(page.getByText(/^courses$/i).first()).toBeVisible()

    // User table headers
    await expect(page.getByRole('columnheader', { name: /email/i })).toBeVisible()
    await expect(page.getByRole('columnheader', { name: /role/i })).toBeVisible()
    await expect(page.getByRole('columnheader', { name: /tier/i })).toBeVisible()
  })

  test('admin page does not expose data to non-admin sessions', async ({ page }) => {
    // A fresh context carries no cookie, so it has no admin session.
    const resp = await page.request.get(`${API_URL}/api/admin/metrics`)
    expect(resp.ok()).toBeFalsy()

    await page.goto('/admin')
    await settle(page)

    // The user table must not be populated for a non-admin session
    const rows = page.getByRole('columnheader', { name: /email/i })
    const hasTable = await rows.isVisible().catch(() => false)
    expect(hasTable).toBeFalsy()
  })
})
