import { test, expect } from './fixtures'

const API_URL = process.env.E2E_API_URL || 'http://localhost:8000'

test.describe('Admin', () => {
  test('admin API is role-gated', async ({ page }) => {
    const resp = await page.request.get(`${API_URL}/api/admin/metrics`)
    if (resp.ok()) {
      // Session is already an admin — gating can't be observed here
      test.skip()
      return
    }
    // Without an authenticated admin the endpoint must reject the request
    expect([401, 403]).toContain(resp.status())
  })

  test('admin page renders metrics and user table for admins', async ({ page }) => {
    const resp = await page.request.get(`${API_URL}/api/admin/metrics`)
    if (!resp.ok()) {
      // Not an admin session (e.g. self-hosted without login) — skip render check
      test.skip()
      return
    }

    await page.goto('/admin')
    await expect(page.getByRole('heading', { name: /admin/i })).toBeVisible({ timeout: 10_000 })
    await page.waitForLoadState('networkidle')

    // Metrics cards
    await expect(page.getByText(/^users$/i).first()).toBeVisible()
    await expect(page.getByText(/^courses$/i).first()).toBeVisible()

    // User table headers
    await expect(page.getByRole('columnheader', { name: /email/i })).toBeVisible()
    await expect(page.getByRole('columnheader', { name: /role/i })).toBeVisible()
    await expect(page.getByRole('columnheader', { name: /tier/i })).toBeVisible()
  })

  test('admin page does not expose data to non-admin sessions', async ({ page }) => {
    const resp = await page.request.get(`${API_URL}/api/admin/metrics`)
    if (resp.ok()) {
      test.skip()
      return
    }

    await page.goto('/admin')
    await page.waitForLoadState('networkidle')

    // The user table must not be populated for a non-admin session
    const rows = page.getByRole('columnheader', { name: /email/i })
    const hasTable = await rows.isVisible().catch(() => false)
    expect(hasTable).toBeFalsy()
  })
})
