import type { BrowserContext, Page } from '@playwright/test'
import { test, expect, testEmail, seedSession, openSession, closeSession } from './fixtures'

// M34 (M34-QA-015): Settings -> AI providers when the server says Claude Code
// cannot run here (settings.claude_code_available / claude_code_unavailable_reason)
// and when it refuses a save with a 422 whose `detail` is a sentence for the user.
//
// The CI stack cannot be made to refuse Claude Code: its API runs as root with
// SINGLE_USER_MODE=true, both of which make claude_cli_unavailable_reason() None.
// So the refusal cases fulfil /api/settings statically (the real settings body
// with the availability fields rewritten) and the one test that talks to the real
// API only asserts that the page agrees with whatever the API reports.

const API_URL = process.env.E2E_API_URL || 'http://localhost:8000'
const PASSWORD = 'TestPass123!'

const REASON =
  'Claude Code is turned off on this server: it runs as one shared system user, so your lectures could be read by other accounts. Pick another provider.'
const SAVE_REFUSAL = 'Claude Code cannot be used on this server. Choose Anthropic API, OpenAI or StudyAIO provided.'

type SettingsBody = Record<string, unknown> & {
  agent_backend: string
  claude_code_available: boolean
  claude_code_unavailable_reason: string | null
}

async function realSettings(context: BrowserContext): Promise<SettingsBody> {
  const resp = await context.request.get(`${API_URL}/api/settings`)
  expect(resp.status()).toBe(200)
  return (await resp.json()) as SettingsBody
}

/**
 * Serve `body` for GET /api/settings, and `onPut` for PUT. Both bodies are
 * built before the page loads and fulfilled statically, so no handler is left
 * waiting on a network call when the context closes.
 */
async function mockSettings(
  context: BrowserContext,
  body: SettingsBody,
  onPut: { status: number; json: unknown } | null = null,
): Promise<{ puts: unknown[] }> {
  const seen: { puts: unknown[] } = { puts: [] }
  await context.route('**/api/settings', (route) => {
    const req = route.request()
    if (req.method() === 'PUT') {
      // The app also saves its own housekeeping (the detected time zone) through this
      // route; only the provider choice is under test, so only that gets the scripted answer.
      const sent = req.postDataJSON() as Record<string, unknown>
      if (!('agent_backend' in sent)) return route.fulfill({ json: body })
      seen.puts.push(sent)
      return route.fulfill({ status: onPut?.status ?? 200, json: onPut?.json ?? body })
    }
    return route.fulfill({ json: body })
  })
  return seen
}

const provider = (page: Page, name: RegExp | string) => page.getByRole('button', { name })
const claude = (page: Page) => provider(page, /Claude Code CLI/)

async function userContext(browser: import('@playwright/test').Browser, opts = {}) {
  return openSession(browser, seedSession(testEmail(), PASSWORD), opts)
}

test.describe('AI providers: Claude Code availability', () => {
  test('when unavailable the option is disabled and says why', async ({ browser }) => {
    const context = await userContext(browser)
    const base = await realSettings(context)
    const seen = await mockSettings(context, {
      ...base,
      agent_backend: 'studyaio',
      claude_code_available: false,
      claude_code_unavailable_reason: REASON,
    })
    const page = await context.newPage()
    await page.goto('/settings/ai')
    await expect(page.getByRole('heading', { name: 'AI Providers' })).toBeVisible({ timeout: 15_000 })

    await expect(claude(page)).toBeDisabled()
    await expect(claude(page)).toHaveAttribute('aria-pressed', 'false')
    await expect(claude(page).getByText(REASON)).toBeVisible()
    // The reason is wired to the control for assistive tech, not just painted next to it.
    const describedBy = await claude(page).getAttribute('aria-describedby')
    expect(describedBy).toBe('provider-claude_code-reason')
    await expect(page.locator(`#${describedBy}`)).toHaveText(REASON)

    // The others are untouched, and the current choice is still the active one.
    await expect(provider(page, /StudyAIO provided/)).toHaveAttribute('aria-pressed', 'true')
    await expect(provider(page, /Anthropic API/)).toBeEnabled()
    await expect(provider(page, /^OpenAI/)).toBeEnabled()

    // Forcing a click on the disabled option sends nothing.
    await claude(page).click({ force: true })
    expect(seen.puts).toEqual([])
    await closeSession(context)
  })

  test('with Claude Code already saved it stays selected, marked unavailable, and can be switched away from', async ({
    browser,
  }) => {
    const context = await userContext(browser)
    const base = await realSettings(context)
    const unavailable = {
      ...base,
      agent_backend: 'claude_code',
      claude_code_available: false,
      claude_code_unavailable_reason: REASON,
    }
    const seen = await mockSettings(context, unavailable, {
      status: 200,
      json: { ...unavailable, agent_backend: 'anthropic_api' },
    })
    const page = await context.newPage()
    await page.goto('/settings/ai')
    await expect(page.getByRole('heading', { name: 'AI Providers' })).toBeVisible({ timeout: 15_000 })

    // Selected, not disabled (the user can still see and leave it), and flagged.
    await expect(claude(page)).toHaveAttribute('aria-pressed', 'true')
    await expect(claude(page)).toBeEnabled()
    await expect(claude(page).getByText('unavailable', { exact: true })).toBeVisible()
    await expect(claude(page).getByText('active', { exact: true })).toHaveCount(0)
    await expect(claude(page).getByText(REASON, { exact: false })).toBeVisible()
    await expect(claude(page).getByText('Pick another provider to keep using the AI.')).toBeVisible()

    // Leaving it is a normal save.
    await provider(page, /Anthropic API/).click()
    await expect.poll(() => seen.puts).toEqual([{ agent_backend: 'anthropic_api' }])
    await expect(provider(page, /Anthropic API/)).toHaveAttribute('aria-pressed', 'true')
    await closeSession(context)
  })

  test('a 422 on save shows the server sentence as written and puts the selector back', async ({ browser }) => {
    const context = await userContext(browser)
    const base = await realSettings(context)
    const available = {
      ...base,
      agent_backend: 'studyaio',
      claude_code_available: true,
      claude_code_unavailable_reason: null,
    }
    const seen = await mockSettings(context, available, { status: 422, json: { detail: SAVE_REFUSAL } })
    const page = await context.newPage()
    await page.goto('/settings/ai')
    await expect(page.getByRole('heading', { name: 'AI Providers' })).toBeVisible({ timeout: 15_000 })
    await expect(claude(page)).toBeEnabled()

    await claude(page).click()
    await expect.poll(() => seen.puts).toEqual([{ agent_backend: 'claude_code' }])
    // Verbatim: not "the request was invalid", not a toast that disappears.
    const alert = page.getByRole('alert').filter({ hasText: SAVE_REFUSAL })
    await expect(alert).toBeVisible()
    await expect(alert).toHaveText(SAVE_REFUSAL)
    await expect(provider(page, /StudyAIO provided/)).toHaveAttribute('aria-pressed', 'true')
    await expect(claude(page)).toHaveAttribute('aria-pressed', 'false')
    await closeSession(context)
  })

  test('Test connection shows a 422 detail as written', async ({ browser }) => {
    const context = await userContext(browser)
    const base = await realSettings(context)
    await mockSettings(context, {
      ...base,
      agent_backend: 'claude_code',
      claude_code_available: false,
      claude_code_unavailable_reason: REASON,
    })
    await context.route('**/api/settings/test-ai', (route) =>
      route.fulfill({ status: 422, json: { detail: REASON } }),
    )
    const page = await context.newPage()
    await page.goto('/settings/ai')
    await expect(claude(page)).toHaveAttribute('aria-pressed', 'true', { timeout: 15_000 })
    await page.getByRole('button', { name: 'Test connection' }).click()
    await expect(page.getByRole('status').filter({ hasText: REASON })).toHaveText(REASON)
    await closeSession(context)
  })

  test('against the real API the page agrees with what the server reports', async ({ browser }) => {
    const context = await userContext(browser)
    const real = await realSettings(context)
    expect(typeof real.claude_code_available).toBe('boolean')
    // The reason is present exactly when the option is unavailable.
    expect(real.claude_code_unavailable_reason === null).toBe(real.claude_code_available)
    const page = await context.newPage()
    await page.goto('/settings/ai')
    await expect(page.getByRole('heading', { name: 'AI Providers' })).toBeVisible({ timeout: 15_000 })
    if (real.claude_code_available) {
      await expect(claude(page)).toBeEnabled()
    } else {
      await expect(claude(page)).toBeDisabled()
      await expect(claude(page).getByText(real.claude_code_unavailable_reason as string)).toBeVisible()
    }
    await closeSession(context)
  })

  test('at 375px the unavailable option and its reason fit without horizontal scroll', async ({ browser }) => {
    const context = await userContext(browser, { viewport: { width: 375, height: 667 } })
    const base = await realSettings(context)
    await mockSettings(context, {
      ...base,
      agent_backend: 'claude_code',
      claude_code_available: false,
      claude_code_unavailable_reason: REASON,
    })
    const page = await context.newPage()
    await page.goto('/settings/ai')
    await expect(claude(page)).toHaveAttribute('aria-pressed', 'true', { timeout: 15_000 })
    await expect(claude(page).getByText(REASON, { exact: false })).toBeVisible()
    const m = await page.evaluate(() => ({
      scroll: document.documentElement.scrollWidth,
      inner: window.innerWidth,
    }))
    expect(m.scroll).toBeLessThanOrEqual(m.inner)
    const box = (await provider(page, /StudyAIO provided/).boundingBox())!
    expect(box.height).toBeGreaterThanOrEqual(44)
    await closeSession(context)
  })
})
