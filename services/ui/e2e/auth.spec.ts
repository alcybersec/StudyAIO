import { test, expect, testEmail } from './fixtures'

const API_URL = process.env.E2E_API_URL || 'http://localhost:8000'

// Every test here runs in both auth modes. The register and login endpoints and
// pages are not gated on SELF_HOSTED (the server gates registration on
// REGISTRATION_MODE only), so the account flows are exercised the same way in
// the self-hosted stack CI runs and in a hosted one. Only the two behaviours
// that genuinely differ by mode -- the unauthenticated redirect and demo login
// -- branch, and each branch asserts its mode's contract instead of skipping.
test.describe('Authentication', () => {
  test('register creates a new account and redirects to dashboard', async ({ page }) => {
    const email = testEmail()
    await page.goto('/register')
    await page.getByLabel(/email/i).fill(email)
    await page.getByLabel(/username/i).fill(email.split('@')[0])
    await page.getByLabel(/^password$/i).fill('TestPass123!')
    await page.getByLabel(/confirm/i).fill('TestPass123!')
    await page.getByRole('button', { name: /create account/i }).click()
    await expect(page).toHaveURL('/', { timeout: 10_000 })
  })

  test('login with valid credentials reaches dashboard', async ({ page }) => {
    // Register then login
    const email = testEmail()
    const password = 'TestPass123!'
    const registered = await page.request.post(`${API_URL}/api/auth/register`, {
      data: { email, password, username: email.split('@')[0] },
    })
    expect(registered.ok()).toBeTruthy()
    await page.context().clearCookies()

    await page.goto('/login')
    await page.getByLabel(/email/i).fill(email)
    await page.getByLabel(/password/i).fill(password)
    await page.getByRole('button', { name: /log in|sign in/i }).click()
    await expect(page).toHaveURL('/', { timeout: 10_000 })
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible({ timeout: 10_000 })
  })

  test('login with wrong password shows error', async ({ page }) => {
    await page.goto('/login')
    await page.getByLabel(/email/i).fill('nonexistent@example.com')
    await page.getByLabel(/password/i).fill('wrongpassword')
    await page.getByRole('button', { name: /log in|sign in/i }).click()
    await expect(page.getByText(/wrong email or password/i)).toBeVisible({ timeout: 5_000 })
  })

  test('demo login follows the instance configuration', async ({ page }) => {
    const authConfig = await (await page.request.get(`${API_URL}/api/auth/config`)).json()

    if (authConfig.demo_enabled) {
      await page.request.get(`${API_URL}/api/auth/demo-login`)
    } else {
      // Disabled demo mode must not hand out a session
      const resp = await page.request.get(`${API_URL}/api/auth/demo-login`, { maxRedirects: 0 })
      expect(resp.status()).toBe(404)
    }

    // Either way the dashboard is reachable: via the demo session, or because
    // a self-hosted instance needs no login at all.
    if (authConfig.demo_enabled || authConfig.self_hosted) {
      await page.goto('/')
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible({ timeout: 10_000 })
    }
  })

  test('unauthenticated access follows the instance auth mode', async ({ page }) => {
    const authConfig = await (await page.request.get(`${API_URL}/api/auth/config`)).json()

    await page.context().clearCookies()
    await page.goto('/upload')

    if (authConfig.self_hosted) {
      // Self-hosted bypasses auth: the protected route renders, no redirect
      await expect(page.getByRole('heading', { name: /upload/i })).toBeVisible({ timeout: 10_000 })
      await expect(page).not.toHaveURL(/\/login/)
    } else {
      await expect(page).toHaveURL(/\/login/, { timeout: 10_000 })
    }
  })
})
