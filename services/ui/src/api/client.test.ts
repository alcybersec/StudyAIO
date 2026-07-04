import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, setRequestTimeout } from './client'
import {
  AppApiError,
  NetworkError,
  NotFoundError,
  RateLimitError,
  ServerError,
  ValidationError,
  classifyResponse,
} from './errors'

function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  })
}

describe('classifyResponse', () => {
  it('maps 400 with field map detail to ValidationError with fields', () => {
    const err = classifyResponse(400, { detail: { email: 'Invalid email address' } })
    expect(err).toBeInstanceOf(ValidationError)
    expect((err as ValidationError).fields).toEqual({ email: 'Invalid email address' })
    expect(err.status).toBe(400)
  })

  it('maps 404 to NotFoundError', () => {
    const err = classifyResponse(404, { detail: 'Course not found' })
    expect(err).toBeInstanceOf(NotFoundError)
    expect(err.message).toBe('Course not found')
  })

  it('maps 429 to RateLimitError with retry-after seconds', () => {
    const err = classifyResponse(429, { detail: 'Rate limit exceeded' }, 42)
    expect(err).toBeInstanceOf(RateLimitError)
    expect((err as RateLimitError).retryAfterSeconds).toBe(42)
  })

  it('defaults RateLimitError.retryAfterSeconds to 30 without a header', () => {
    const err = classifyResponse(429, { detail: 'Slow down' })
    expect((err as RateLimitError).retryAfterSeconds).toBe(30)
  })

  it('maps 5xx to ServerError', () => {
    expect(classifyResponse(500, { detail: 'boom' })).toBeInstanceOf(ServerError)
    expect(classifyResponse(502, {})).toBeInstanceOf(ServerError)
  })

  it('maps other statuses to base AppApiError', () => {
    const err = classifyResponse(401, { detail: 'Invalid credentials' })
    expect(err).toBeInstanceOf(AppApiError)
    expect(err).not.toBeInstanceOf(ValidationError)
    expect(err).not.toBeInstanceOf(ServerError)
    expect(err.message).toBe('Invalid credentials')
  })
})

describe('api client error taxonomy', () => {
  beforeEach(() => {
    setRequestTimeout(30_000)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('throws ValidationError with fields on 400 field-map detail', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse(400, { detail: { title: 'Title is required' } })),
    )
    const err = await api.post('/exams', {}).catch((e) => e as ValidationError)
    expect(err).toBeInstanceOf(ValidationError)
    expect((err as ValidationError).fields).toEqual({ title: 'Title is required' })
  })

  it('throws NotFoundError on 404', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse(404, { detail: 'Not found' })),
    )
    await expect(api.get('/courses/NOPE')).rejects.toBeInstanceOf(NotFoundError)
  })

  it('throws RateLimitError with Retry-After header seconds on 429', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse(429, { detail: 'Rate limit exceeded' }, { 'Retry-After': '42' }),
      ),
    )
    const err = await api.get('/qa').catch((e) => e as RateLimitError)
    expect(err).toBeInstanceOf(RateLimitError)
    expect((err as RateLimitError).retryAfterSeconds).toBe(42)
  })

  it('throws ServerError on 500', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse(500, { detail: 'Internal Server Error' })),
    )
    await expect(api.get('/dashboard')).rejects.toBeInstanceOf(ServerError)
  })

  it('throws NetworkError when fetch rejects', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(api.get('/dashboard')).rejects.toBeInstanceOf(NetworkError)
  })

  it('passes an abort signal to fetch and throws NetworkError on timeout', async () => {
    setRequestTimeout(20)
    const fetchMock = vi.fn(
      (_url: RequestInfo | URL, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          const signal = init?.signal
          expect(signal).toBeInstanceOf(AbortSignal)
          signal?.addEventListener('abort', () =>
            reject(signal.reason ?? new DOMException('The operation timed out.', 'TimeoutError')),
          )
        }),
    )
    vi.stubGlobal('fetch', fetchMock)
    const err = await api.get('/slow').catch((e) => e)
    expect(err).toBeInstanceOf(NetworkError)
    expect(fetchMock).toHaveBeenCalledOnce()
  })

  it('composes the timeout signal with a caller-supplied signal', async () => {
    setRequestTimeout(30_000)
    const controller = new AbortController()
    const fetchMock = vi.fn(
      (_url: RequestInfo | URL, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () =>
            reject(init.signal?.reason ?? new DOMException('Aborted', 'AbortError')),
          )
        }),
    )
    vi.stubGlobal('fetch', fetchMock)
    const pending = api.request<unknown>('/slow', { signal: controller.signal })
    controller.abort()
    const err = await pending.catch((e) => e as Error)
    expect((err as Error).name).toBe('AbortError')
    expect(err instanceof AppApiError).toBe(false)
  })

  it('does not classify successful responses', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(200, { ok: true })))
    await expect(api.get('/dashboard')).resolves.toEqual({ ok: true })
  })
})
