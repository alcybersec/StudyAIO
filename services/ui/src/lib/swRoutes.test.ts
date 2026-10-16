import { describe, expect, it } from 'vitest'
import { isEventStream, isGeneralApiCacheable } from './swRoutes'

const req = (accept?: string) =>
  ({ headers: new Headers(accept ? { accept } : {}) }) as Pick<Request, 'headers'>

describe('isEventStream', () => {
  it('matches the pipeline event stream, with or without a query', () => {
    expect(isEventStream(new URL('http://x/api/uploads/pipeline-events'))).toBe(true)
    expect(isEventStream(new URL('http://x/api/uploads/pipeline-events?artifact_id=1'))).toBe(true)
  })

  it('matches any request that asks for text/event-stream', () => {
    expect(isEventStream(new URL('http://x/api/other'), req('text/event-stream'))).toBe(true)
  })

  it('does not match ordinary API reads', () => {
    expect(isEventStream(new URL('http://x/api/uploads'), req('application/json'))).toBe(false)
  })
})

describe('isGeneralApiCacheable', () => {
  it('excludes the event stream so the browser handles it directly', () => {
    expect(isGeneralApiCacheable(new URL('http://x/api/uploads/pipeline-events'))).toBe(false)
    expect(
      isGeneralApiCacheable(new URL('http://x/api/anything'), req('text/event-stream'))
    ).toBe(false)
  })

  it('still caches ordinary GETs and skips auth and study writes', () => {
    expect(isGeneralApiCacheable(new URL('http://x/api/uploads'))).toBe(true)
    expect(isGeneralApiCacheable(new URL('http://x/api/auth/me'))).toBe(false)
    expect(isGeneralApiCacheable(new URL('http://x/api/study/review'))).toBe(false)
  })
})
