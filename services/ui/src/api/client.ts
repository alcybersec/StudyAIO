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

  async put<T>(path: string, body?: unknown): Promise<T> {
    const response = await fetch(`${BASE_URL}${path}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    })
    return handleResponse<T>(response)
  },

  async delete(path: string): Promise<void> {
    const response = await fetch(`${BASE_URL}${path}`, {
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
    const response = await fetch(`${BASE_URL}${path}`, {
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
    const response = await fetch(`${BASE_URL}${path}`, {
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
