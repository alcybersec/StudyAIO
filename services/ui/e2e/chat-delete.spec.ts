import { test, expect } from './fixtures'
import type { APIRequestContext, Page } from '@playwright/test'

// GL#52: deleting a conversation asks first. Sessions are created through the
// API with a unique title (no AI is involved; nothing is sent to a provider).

const API_URL = process.env.E2E_API_URL || 'http://localhost:8000'

async function makeSession(request: APIRequestContext): Promise<{ id: string; title: string }> {
  const title = `qa-chat-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
  const resp = await request.post(`${API_URL}/api/chat/sessions`, { data: { title } })
  expect(resp.status()).toBe(201)
  return { id: (await resp.json()).id, title }
}

async function sessionIds(request: APIRequestContext): Promise<string[]> {
  const resp = await request.get(`${API_URL}/api/chat/sessions`)
  expect(resp.ok()).toBeTruthy()
  return ((await resp.json()).sessions as { id: string }[]).map((s) => s.id)
}

/** The rail row (a div holding the select and delete buttons) for this title. */
const row = (page: Page, title: string) => page.locator('aside div.group').filter({ hasText: title })

test.describe('Ask: deleting a conversation', () => {
  let session: { id: string; title: string }

  test.beforeEach(async ({ request }) => {
    session = await makeSession(request)
  })

  test.afterEach(async ({ request }) => {
    // A no-op (404) when the test already deleted it.
    await request.delete(`${API_URL}/api/chat/sessions/${session.id}`)
  })

  test('Cancel and Escape keep the chat; confirming deletes it', async ({ page, request }) => {
    await page.goto(`/ask?session=${session.id}`)
    await expect(row(page, session.title)).toBeVisible({ timeout: 10_000 })
    const dialog = page.getByRole('dialog', { name: 'Delete this conversation?' })
    const open = () => row(page, session.title).getByRole('button', { name: 'Delete conversation' }).click()

    // The click alone never deletes: a dialog names the conversation first.
    await open()
    await expect(dialog).toBeVisible()
    await expect(dialog.getByText(session.title)).toBeVisible()
    await expect(dialog.getByText(/messages? will be permanently deleted/)).toBeVisible()
    expect(await sessionIds(request)).toContain(session.id)

    // Cancel holds focus: Enter dismisses.
    await expect(dialog.getByRole('button', { name: 'Cancel' })).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(dialog).toBeHidden()
    await expect(row(page, session.title)).toBeVisible()
    expect(await sessionIds(request)).toContain(session.id)

    await open()
    await page.keyboard.press('Escape')
    await expect(dialog).toBeHidden()
    expect(await sessionIds(request)).toContain(session.id)

    await open()
    await dialog.getByRole('button', { name: 'Cancel' }).click()
    await expect(dialog).toBeHidden()
    await expect(row(page, session.title)).toBeVisible()
    expect(await sessionIds(request)).toContain(session.id)

    await open()
    await dialog.getByRole('button', { name: 'Delete', exact: true }).click()
    await expect(dialog).toBeHidden()
    await expect(row(page, session.title)).toHaveCount(0)
    expect(await sessionIds(request)).not.toContain(session.id)
  })
})

test.describe('Ask: deleting a conversation in Russian', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => window.localStorage.setItem('studyaio-language', 'ru'))
  })

  test('the confirmation is translated and Cancel still holds focus', async ({ page, request }) => {
    const session = await makeSession(request)
    try {
      await page.goto(`/ask?session=${session.id}`)
      await row(page, session.title).getByRole('button', { name: 'Удалить разговор' }).click()
      const dialog = page.getByRole('dialog', { name: 'Удалить этот разговор?' })
      await expect(dialog).toBeVisible()
      await expect(dialog.getByRole('button', { name: 'Отмена' })).toBeFocused()
      await page.keyboard.press('Escape')
      await expect(dialog).toBeHidden()
      expect(await sessionIds(request)).toContain(session.id)
    } finally {
      await request.delete(`${API_URL}/api/chat/sessions/${session.id}`)
    }
  })
})

test.describe('Ask: delete confirmation at 375px', () => {
  test.use({ viewport: { width: 375, height: 667 } })

  test('the dialog fits and its buttons are tappable', async ({ page, request }) => {
    const session = await makeSession(request)
    try {
      await page.goto(`/ask?session=${session.id}`)
      await page.getByRole('button', { name: 'Open sessions list' }).click()
      const sheetRow = page.locator('div.group').filter({ hasText: session.title })
      await sheetRow.getByRole('button', { name: 'Delete conversation' }).click()
      const dialog = page.getByRole('dialog', { name: 'Delete this conversation?' })
      await expect(dialog).toBeVisible()
      const box = await dialog.boundingBox()
      expect(box!.x).toBeGreaterThanOrEqual(0)
      expect(box!.x + box!.width).toBeLessThanOrEqual(375)
      for (const name of ['Cancel', 'Delete']) {
        const b = await dialog.getByRole('button', { name, exact: true }).boundingBox()
        expect(b!.height).toBeGreaterThanOrEqual(44)
      }
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      )
      expect(overflow).toBe(true)
      await page.keyboard.press('Escape')
      expect(await sessionIds(request)).toContain(session.id)
    } finally {
      await request.delete(`${API_URL}/api/chat/sessions/${session.id}`)
    }
  })
})
