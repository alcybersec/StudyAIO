const BASE_URL = '/api'

class ApiError extends Error {
  status: number
  detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
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

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))

    // Trigger upgrade prompt on 402
    if (response.status === 402 && body.resource && onQuotaExceeded) {
      onQuotaExceeded({ resource: body.resource, limit: body.limit, period: body.period })
    }

    // Trigger demo restriction modal on 403 with upgrade_url
    if (response.status === 403 && body.upgrade_url && onDemoRestriction) {
      onDemoRestriction()
    }

    throw new ApiError(response.status, body.detail || response.statusText)
  }
  return response.json()
}

export const api = {
  async get<T>(path: string): Promise<T> {
    const response = await fetchWithRefresh(`${BASE_URL}${path}`)
    return handleResponse<T>(response)
  },

  async post<T>(path: string, body?: unknown): Promise<T> {
    const response = await fetchWithRefresh(`${BASE_URL}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    })
    return handleResponse<T>(response)
  },

  async put<T>(path: string, body?: unknown): Promise<T> {
    const response = await fetchWithRefresh(`${BASE_URL}${path}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    })
    return handleResponse<T>(response)
  },

  async patch<T>(path: string, body?: unknown): Promise<T> {
    const response = await fetchWithRefresh(`${BASE_URL}${path}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    })
    return handleResponse<T>(response)
  },

  async delete(path: string): Promise<void> {
    const response = await fetchWithRefresh(`${BASE_URL}${path}`, {
      method: 'DELETE',
    })
    if (!response.ok) {
      const body = await response.json().catch(() => ({ detail: response.statusText }))
      throw new ApiError(response.status, body.detail || response.statusText)
    }
  },

  async upload<T>(path: string, file: File): Promise<T> {
    const formData = new FormData()
    formData.append('file', file)
    const response = await fetchWithRefresh(`${BASE_URL}${path}`, {
      method: 'POST',
      body: formData,
    })
    return handleResponse<T>(response)
  },

  async uploadMany<T>(path: string, files: File[]): Promise<T> {
    const formData = new FormData()
    for (const file of files) {
      formData.append('files', file)
    }
    const response = await fetchWithRefresh(`${BASE_URL}${path}`, {
      method: 'POST',
      body: formData,
    })
    return handleResponse<T>(response)
  },

  downloadUrl(path: string): string {
    return `${BASE_URL}${path}`
  },
}

export { ApiError }
