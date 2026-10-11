import { execFileSync } from 'node:child_process'
import path from 'node:path'
import { test as base, expect, type APIRequestContext, type Page } from '@playwright/test'

const API_URL = process.env.E2E_API_URL || 'http://localhost:8000'

/** Generate a unique test email */
export function testEmail(): string {
  return `e2e_${Date.now()}_${Math.random().toString(36).slice(2, 8)}@example.com`
}

/** Register a new user via the API and return credentials */
export async function registerUser(page: Page): Promise<{ email: string; password: string }> {
  const email = testEmail()
  const password = 'TestPass123!'
  const resp = await page.request.post(`${API_URL}/api/auth/register`, {
    data: { email, password, username: email.split('@')[0] },
  })
  expect(resp.ok()).toBeTruthy()
  return { email, password }
}

/** Login via API and set cookies on the page context */
export async function loginViaAPI(
  page: Page,
  email: string,
  password: string,
): Promise<void> {
  const resp = await page.request.post(`${API_URL}/api/auth/login`, {
    data: { email, password },
  })
  expect(resp.ok()).toBeTruthy()
}

/**
 * Record AI-processing consent for the logged-in user. AI-spending routes
 * (uploads, chat, Q&A, ...) answer 403 `ai_consent_required` until this is
 * called; a single-user stack never asks, so it is a harmless 200 there.
 */
export async function giveAiConsent(page: Page): Promise<void> {
  const resp = await page.request.post(`${API_URL}/api/auth/consent`)
  expect(resp.ok()).toBeTruthy()
  const body = await resp.json()
  expect(body.ai_consent_required).toBe(false)
}

/** Login via the demo endpoint (self-hosted shortcut) */
export async function loginAsDemo(page: Page): Promise<void> {
  const resp = await page.request.get(`${API_URL}/api/auth/demo-login`)
  expect(resp.ok()).toBeTruthy()
}

/** Seed a course + artifact via API for tests that need data */
export async function seedCourse(
  page: Page,
  courseCode = 'E2ETEST',
): Promise<{ courseId: string }> {
  // Check if course already exists
  const list = await page.request.get(`${API_URL}/api/courses`)
  const courses = await list.json()
  const existing = courses.find((c: { code: string }) => c.code === courseCode)
  if (existing) return { courseId: existing.id }

  // Upload a minimal test PDF to create the course
  const pdfBytes = buildMinimalPDF()
  const resp = await page.request.post(`${API_URL}/api/upload`, {
    multipart: {
      file: {
        name: `${courseCode}_week1.pdf`,
        mimeType: 'application/pdf',
        buffer: Buffer.from(pdfBytes),
      },
    },
  })
  expect(resp.ok()).toBeTruthy()
  const data = await resp.json()
  return { courseId: data.course_id || data.id }
}

/**
 * Run e2e/seed_e2e.py for rows the public API cannot create (a course exists
 * only as a side effect of the classify stage; the CI job runs no worker).
 * Needs DATABASE_URL_SYNC in the environment, as the e2e-tests job provides.
 * Fails loudly -- a missing seed must never turn into a skipped test.
 */
export function seedDb(...args: string[]): void {
  const script = path.resolve(process.cwd(), 'e2e', 'seed_e2e.py')
  try {
    execFileSync(process.env.E2E_PYTHON || 'python3', [script, ...args], {
      stdio: 'pipe',
      env: process.env,
    })
  } catch (err) {
    const e = err as { stderr?: Buffer; message: string }
    throw new Error(`seed_e2e.py ${args.join(' ')} failed: ${e.stderr?.toString() || e.message}`)
  }
}

/** Seed a course (and optional concepts) owned by the self-hosted default user. */
export function seedCourseRow(code: string, concepts = 0): void {
  seedDb('course', code, '--concepts', String(concepts))
}

/** Delete a seeded course (and its children) through the public API. */
export async function deleteCourse(request: APIRequestContext, code: string): Promise<void> {
  const resp = await request.delete(`${API_URL}/api/courses/${code}`, {
    headers: { 'X-Confirm': code },
  })
  expect([200, 404]).toContain(resp.status())
}

/** Build a minimal valid PDF for upload tests */
function buildMinimalPDF(): Uint8Array {
  const content = `%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<</Font<</F1 4 0 R>>>>>>endobj
4 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000236 00000 n
trailer<</Size 5/Root 1 0 R>>
startxref
310
%%EOF`
  return new TextEncoder().encode(content)
}

export { base as test, expect }
