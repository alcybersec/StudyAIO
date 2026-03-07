import { test, expect, testEmail } from './fixtures'

const API_URL = process.env.E2E_API_URL || 'http://localhost:8000'

test.describe('Authentication', () => {
  test('register creates a new account and redirects to dashboard', async ({ page }) => {
    // Check if registration is enabled (non-self-hosted)
    const config = await page.request.get(`${API_URL}/api/auth/config`)
    const authConfig = await config.json()

    if (authConfig.self_hosted) {
      test.skip()
      return
    }

    const email = testEmail()
    await page.goto('/register')
    await page.getByLabel(/email/i).fill(email)
    await page.getByLabel(/username/i).fill(email.split('@')[0])
    await page.getByLabel(/^password$/i).fill('TestPass123!')
    await page.getByLabel(/confirm/i).fill('TestPass123!')
    await page.getByRole('button', { name: /register|sign up/i }).click()
    await expect(page).toHaveURL('/', { timeout: 10_000 })
  })

  test('login with valid credentials reaches dashboard', async ({ page }) => {
    const config = await page.request.get(`${API_URL}/api/auth/config`)
    const authConfig = await config.json()

    if (authConfig.self_hosted) {
      // Self-hosted mode — just visit dashboard directly
      await page.goto('/')
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible({ timeout: 10_000 })
      return
    }

    // Register then login
    const email = testEmail()
    const password = 'TestPass123!'
    await page.request.post(`${API_URL}/api/auth/register`, {
      data: { email, password, username: email.split('@')[0] },
    })

    await page.goto('/login')
    await page.getByLabel(/email/i).fill(email)
    await page.getByLabel(/password/i).fill(password)
    await page.getByRole('button', { name: /log in|sign in/i }).click()
    await expect(page).toHaveURL('/', { timeout: 10_000 })
  })

  test('login with wrong password shows error', async ({ page }) => {
    const config = await page.request.get(`${API_URL}/api/auth/config`)
    const authConfig = await config.json()

    if (authConfig.self_hosted) {
      test.skip()
      return
    }

    await page.goto('/login')
    await page.getByLabel(/email/i).fill('nonexistent@example.com')
    await page.getByLabel(/password/i).fill('wrongpassword')
    await page.getByRole('button', { name: /log in|sign in/i }).click()
    await expect(page.getByText(/invalid|incorrect|error/i)).toBeVisible({ timeout: 5_000 })
  })

  test('demo login reaches dashboard', async ({ page }) => {
    const config = await page.request.get(`${API_URL}/api/auth/config`)
    const authConfig = await config.json()

    if (!authConfig.demo_enabled && !authConfig.self_hosted) {
      test.skip()
      return
    }

    if (authConfig.self_hosted) {
      await page.goto('/')
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible({ timeout: 10_000 })
      return
    }

    // Use demo login endpoint
    await page.request.get(`${API_URL}/api/auth/demo-login`)
    await page.goto('/')
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible({ timeout: 10_000 })
  })

  test('unauthenticated user is redirected to login', async ({ page }) => {
    const config = await page.request.get(`${API_URL}/api/auth/config`)
    const authConfig = await config.json()

    if (authConfig.self_hosted) {
      // Self-hosted bypasses auth
      test.skip()
      return
    }

    // Clear any cookies
    await page.context().clearCookies()
    await page.goto('/upload')
    await expect(page).toHaveURL(/\/login/, { timeout: 10_000 })
  })
})
