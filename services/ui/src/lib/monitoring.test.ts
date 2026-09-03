import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { scrubUrl, initMonitoring, captureError, __resetMonitoringForTests } from './monitoring'

// Not in Sentry's scheme://key@host/id form, to avoid tripping secret
// scanners. initMonitoring only needs a non-empty string, and the SDK is
// mocked below.
const FAKE_DSN = 'sentry-dsn-placeholder'

const initSpy = vi.fn()
const setTagSpy = vi.fn()
const captureExceptionSpy = vi.fn()

vi.mock('@sentry/react', () => ({
  init: (...args: unknown[]) => initSpy(...args),
  setTag: (...args: unknown[]) => setTagSpy(...args),
  captureException: (...args: unknown[]) => captureExceptionSpy(...args),
}))

describe('scrubUrl', () => {
  it('filters a reset-password token out of the URL', () => {
    const out = scrubUrl('https://app.test/reset-password?token=super-secret')
    expect(out).not.toContain('super-secret')
    expect(out).toContain('token=%5BFiltered%5D')
  })

  it('filters an invite code', () => {
    const out = scrubUrl('https://app.test/register?invite_code=BETA-1')
    expect(out).not.toContain('BETA-1')
  })

  it('leaves non-sensitive params alone', () => {
    const out = scrubUrl('https://app.test/courses?week=5')
    expect(out).toContain('week=5')
  })

  it('returns the URL unchanged when there is nothing to scrub', () => {
    expect(scrubUrl('https://app.test/home')).toBe('https://app.test/home')
  })

  it('does not throw on a malformed URL', () => {
    expect(() => scrubUrl('::::not a url::::')).not.toThrow()
  })
})

describe('initMonitoring', () => {
  beforeEach(() => {
    __resetMonitoringForTests()
    initSpy.mockReset()
    setTagSpy.mockReset()
  })

  afterEach(() => {
    vi.unstubAllEnvs()
    __resetMonitoringForTests()
  })

  it('resolves false and loads nothing when no DSN is configured', async () => {
    vi.stubEnv('VITE_SENTRY_DSN', '')
    await expect(initMonitoring()).resolves.toBe(false)
  })

  it('treats a whitespace-only DSN as unset', async () => {
    vi.stubEnv('VITE_SENTRY_DSN', '   ')
    await expect(initMonitoring()).resolves.toBe(false)
  })

  it('initializes with safe defaults when a DSN is set', async () => {
    vi.stubEnv('VITE_SENTRY_DSN', FAKE_DSN)
    vi.stubEnv('VITE_SENTRY_ENVIRONMENT', 'beta')

    await expect(initMonitoring()).resolves.toBe(true)

    expect(initSpy).toHaveBeenCalledOnce()
    const options = initSpy.mock.calls[0][0]
    expect(options.dsn).toBe(FAKE_DSN)
    expect(options.environment).toBe('beta')
    expect(options.sendDefaultPii).toBe(false)
  })

  it('scrubs credential-bearing URLs before sending', async () => {
    vi.stubEnv('VITE_SENTRY_DSN', FAKE_DSN)
    await initMonitoring()

    const { beforeSend } = initSpy.mock.calls[0][0]
    const event = { request: { url: 'https://app.test/reset-password?token=super-secret' } }
    const sent = beforeSend(event)
    expect(sent.request.url).not.toContain('super-secret')
  })

  it('resolves false rather than throwing when the SDK fails to load', async () => {
    // Ad blockers routinely block Sentry; that must not break the app.
    initSpy.mockImplementationOnce(() => {
      throw new Error('blocked')
    })
    vi.stubEnv('VITE_SENTRY_DSN', FAKE_DSN)
    await expect(initMonitoring()).resolves.toBe(false)
  })

  it('only attempts initialization once', async () => {
    vi.stubEnv('VITE_SENTRY_DSN', '')
    const first = initMonitoring()
    const second = initMonitoring()
    expect(first).toBe(second)
  })
})

describe('captureError', () => {
  beforeEach(() => {
    __resetMonitoringForTests()
  })

  it('is a silent no-op when monitoring is disabled', () => {
    expect(() => captureError(new Error('boom'))).not.toThrow()
  })

  it('accepts extra context without throwing', () => {
    expect(() => captureError(new Error('boom'), { route: '/courses' })).not.toThrow()
  })
})
