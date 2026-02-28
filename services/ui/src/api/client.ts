const BASE_URL = '/api'

class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail)
    this.name = 'ApiError'
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    throw new ApiError(response.status, body.detail || response.statusText)
  }
  return response.json()
}

export const api = {
  async get<T>(path: string): Promise<T> {
    const response = await fetch(`${BASE_URL}${path}`)
    return handleResponse<T>(response)
  },

  async post<T>(path: string, body?: unknown): Promise<T> {
    const response = await fetch(`${BASE_URL}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    })
    return handleResponse<T>(response)
  },

  async upload<T>(path: string, file: File): Promise<T> {
    const formData = new FormData()
    formData.append('file', file)
    const response = await fetch(`${BASE_URL}${path}`, {
      method: 'POST',
      body: formData,
    })
    return handleResponse<T>(response)
  },
}

export { ApiError }
