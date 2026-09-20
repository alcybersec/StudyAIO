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
      jsonResponse({
        moved_summaries: 2,
        conflict_weeks: [],
        conflict_resolution: 'regenerate',
        regenerated_weeks: [],
      }),
    )

    await coursesApi.merge('CSIT302', 'CSCI368')

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/courses/CSIT302/merge')
    expect(init.method).toBe('POST')
    // on_conflict is omitted rather than sent as undefined, so the server's own
    // default applies instead of the client pinning one it did not choose.
    expect(JSON.parse(init.body as string)).toEqual({ into: 'CSCI368' })
  })

  it('merge forwards an explicit conflict policy', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        moved_summaries: 0,
        conflict_weeks: [3],
        conflict_resolution: 'keep_target',
        regenerated_weeks: [],
      }),
    )

    const result = await coursesApi.merge('CSIT302', 'CSCI368', 'keep_target')

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(JSON.parse(init.body as string)).toEqual({
      into: 'CSCI368',
      on_conflict: 'keep_target',
    })
    expect(result.conflict_resolution).toBe('keep_target')
    expect(result.regenerated_weeks).toEqual([])
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
