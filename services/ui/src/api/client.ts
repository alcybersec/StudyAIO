import { AppApiError, NetworkError, classifyResponse } from './errors'

const BASE_URL = '/api'

// Default request timeout — long enough for AI-backed endpoints, short enough
// to surface dead connections as NetworkError instead of hanging forever.
const DEFAULT_TIMEOUT_MS = 30_000
let requestTimeoutMs = DEFAULT_TIMEOUT_MS

/** Test hook: override the default request timeout. */
export function setRequestTimeout(ms: number) {
  requestTimeoutMs = ms
}

function timeoutSignal(ms: number): AbortSignal {
  if (typeof AbortSignal.timeout === 'function') {
    return AbortSignal.timeout(ms)
  }
  // Fallback for environments without AbortSignal.timeout
  const controller = new AbortController()
  setTimeout(
    () => controller.abort(new DOMException('The operation timed out.', 'TimeoutError')),
    ms,
  )
  return controller.signal
}

/** Compose a caller-supplied signal with the default timeout signal. */
function composeSignals(caller: AbortSignal | null | undefined, timeout: AbortSignal): AbortSignal {
  if (!caller) return timeout
  if (typeof AbortSignal.any === 'function') {
    return AbortSignal.any([caller, timeout])
  }
  // Fallback: mirror whichever aborts first onto a fresh controller
  const controller = new AbortController()
  const forward = (signal: AbortSignal) => () => controller.abort(signal.reason)
  if (caller.aborted) controller.abort(caller.reason)
  else caller.addEventListener('abort', forward(caller), { once: true })
  if (timeout.aborted) controller.abort(timeout.reason)
  else timeout.addEventListener('abort', forward(timeout), { once: true })
  return controller.signal
}

// Auth paths that should not trigger auto-refresh
const AUTH_PATHS = ['/auth/login', '/auth/register', '/auth/refresh', '/auth/config']

// Deduplication: only one refresh attempt at a time
let refreshPromise: Promise<boolean> | null = null

async function tryRefresh(): Promise<boolean> {
  if (refreshPromise) return refreshPromise
  refreshPromise = fetch(`${BASE_URL}/auth/refresh`, { method: 'POST' })
    .then((r) => r.ok)
    .catch(() => false)
    .finally(() => {
      refreshPromise = null
    })
  return refreshPromise
}

async function fetchWithRefresh(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const response = await fetch(input, init)
  if (response.status !== 401) return response

  // Don't retry refresh for auth-related paths
  const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
  if (AUTH_PATHS.some((p) => url.includes(p))) return response

  const refreshed = await tryRefresh()
  if (!refreshed) return response

  // Retry the original request
  return fetch(input, init)
}

/**
 * Perform a request with the shared timeout + refresh behavior.
 * Network failures and timeouts are normalized to NetworkError;
 * caller-initiated aborts are re-thrown untouched.
 */
async function request(path: string, init: RequestInit = {}): Promise<Response> {
  const callerSignal = init.signal
  const signal = composeSignals(callerSignal, timeoutSignal(requestTimeoutMs))
  try {
    return await fetchWithRefresh(`${BASE_URL}${path}`, { ...init, signal })
  } catch (err) {
    if (err instanceof AppApiError) throw err
    const name = (err as Error)?.name
    if (name === 'TimeoutError') {
      throw new NetworkError('The request timed out', 0, String(err))
    }
    if (name === 'AbortError') {
      // Distinguish our timeout from a caller-initiated abort
      if (callerSignal?.aborted) throw err
      throw new NetworkError('The request timed out', 0, String(err))
    }
    throw new NetworkError('Network request failed', 0, String(err))
  }
}

// Global quota error handler — set by QuotaProvider
let onQuotaExceeded: ((error: { resource: string; limit: number; period: string }) => void) | null = null

export function setQuotaExceededHandler(handler: typeof onQuotaExceeded) {
  onQuotaExceeded = handler
}

// Global demo restriction handler — set by QuotaProvider
let onDemoRestriction: (() => void) | null = null

export function setDemoRestrictionHandler(handler: typeof onDemoRestriction) {
  onDemoRestriction = handler
}

function parseRetryAfter(response: Response): number | undefined {
  const header = response.headers.get('Retry-After')
  if (!header) return undefined
  const seconds = Number(header)
  return Number.isFinite(seconds) ? seconds : undefined
}

async function raiseForStatus(response: Response): Promise<void> {
  if (response.ok) return
  const body = await response.json().catch(() => ({ detail: response.statusText }))

  // Trigger upgrade prompt on 402
  if (response.status === 402 && body.resource && onQuotaExceeded) {
    onQuotaExceeded({ resource: body.resource, limit: body.limit, period: body.period })
  }

  // Trigger demo restriction modal on 403 with upgrade_url
  if (response.status === 403 && body.upgrade_url && onDemoRestriction) {
    onDemoRestriction()
  }

  throw classifyResponse(response.status, body, parseRetryAfter(response))
}

async function handleResponse<T>(response: Response): Promise<T> {
  await raiseForStatus(response)
  return response.json()
}

export const api = {
  /** Low-level escape hatch: classified errors, raw Response back. */
  async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await request(path, init)
    return handleResponse<T>(response)
  },

  async get<T>(path: string): Promise<T> {
    const response = await request(path)
    return handleResponse<T>(response)
  },

  async post<T>(path: string, body?: unknown): Promise<T> {
    const response = await request(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    })
    return handleResponse<T>(response)
  },

  async put<T>(path: string, body?: unknown): Promise<T> {
    const response = await request(path, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    })
    return handleResponse<T>(response)
  },

  async patch<T>(path: string, body?: unknown): Promise<T> {
    const response = await request(path, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    })
    return handleResponse<T>(response)
  },

  async delete(path: string): Promise<void> {
    const response = await request(path, { method: 'DELETE' })
    await raiseForStatus(response)
  },

  async upload<T>(path: string, file: File): Promise<T> {
    const formData = new FormData()
    formData.append('file', file)
    const response = await request(path, { method: 'POST', body: formData })
    return handleResponse<T>(response)
  },

  async uploadMany<T>(path: string, files: File[]): Promise<T> {
    const formData = new FormData()
    for (const file of files) {
      formData.append('files', file)
    }
    const response = await request(path, { method: 'POST', body: formData })
    return handleResponse<T>(response)
  },

  downloadUrl(path: string): string {
    return `${BASE_URL}${path}`
  },
}

// Backward-compatible alias: existing call-sites check `instanceof ApiError`.
export { AppApiError as ApiError }
