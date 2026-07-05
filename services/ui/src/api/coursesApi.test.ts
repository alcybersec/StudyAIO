import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { coursesApi } from './endpoints'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('coursesApi course management', () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.clearAllMocks()
  })

  it('remove sends DELETE with the X-Confirm header set to the course code', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ code: 'CSIT302', deleted: true, counts: { artifacts: 3 } }),
    )

    const result = await coursesApi.remove('CSIT302')

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/courses/CSIT302')
    expect(init.method).toBe('DELETE')
    expect((init.headers as Record<string, string>)['X-Confirm']).toBe('CSIT302')
    expect(result.deleted).toBe(true)
  })

  it('rename PATCHes the course with new code and name', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ id: '1', code: 'CS999', name: 'New' }))

    await coursesApi.rename('CSIT302', { new_code: 'CS999', name: 'New' })

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/courses/CSIT302')
    expect(init.method).toBe('PATCH')
    expect(JSON.parse(init.body as string)).toEqual({ new_code: 'CS999', name: 'New' })
  })

  it('merge POSTs the target course code', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ moved_summaries: 2, conflict_weeks: [], review_items_created: 0 }),
    )

    await coursesApi.merge('CSIT302', 'CSCI368')

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/courses/CSIT302/merge')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body as string)).toEqual({ into: 'CSCI368' })
  })

  it('archive POSTs to the archive endpoint', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ code: 'CSIT302', archived: true }))

    const result = await coursesApi.archive('CSIT302')

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/courses/CSIT302/archive')
    expect(init.method).toBe('POST')
    expect(result.archived).toBe(true)
  })
})
