import { describe, expect, it, vi } from 'vitest'
import i18n from '../i18n'
import { classifyResponse } from '../api/errors'
import { userErrorMessage } from './userError'
import { mutationErrorContent } from './toast'

const RAW = 'psycopg.errors.UniqueViolation: duplicate key at /app/api/x.py line 12'

describe('userErrorMessage', () => {
  it('never shows the raw detail of a 5xx', () => {
    const msg = userErrorMessage(classifyResponse(500, { detail: RAW }))
    expect(msg).toBe(i18n.t('The server hit a problem'))
    expect(msg).not.toContain('psycopg')
  })

  it.each([
    [401, 'Please sign in again.'],
    [402, 'This is over your plan limit.'],
    [403, "You don't have permission to do that."],
    [404, 'It may have been removed — this item no longer exists.'],
    [409, 'That conflicts with something that already exists.'],
    [413, 'That file is too large.'],
  ])('maps %i to a translated message, not the raw detail', (status, key) => {
    const msg = userErrorMessage(classifyResponse(status, { detail: RAW }))
    expect(msg).toBe(i18n.t(key))
    expect(msg).not.toContain('psycopg')
  })

  it('uses the caller fallback for unmapped 4xx and non-API errors', () => {
    expect(userErrorMessage(classifyResponse(418, { detail: RAW }), 'Fallback')).toBe('Fallback')
    expect(userErrorMessage(new TypeError('x is undefined'), 'Fallback')).toBe('Fallback')
    expect(userErrorMessage(new Error('boom'))).toBe(i18n.t('Something went wrong'))
  })

  it('keeps user-meant 422 field messages', () => {
    const err = classifyResponse(422, {
      detail: [{ loc: ['body', 'email'], msg: 'Enter a valid email address' }],
    })
    expect(userErrorMessage(err)).toBe('Enter a valid email address')
  })

  it('falls back to a generic message for a 422 without fields', () => {
    expect(userErrorMessage(classifyResponse(422, { detail: RAW }))).toBe(
      i18n.t('The request was invalid'),
    )
  })

  it('logs raw text to the console in dev only', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    userErrorMessage(classifyResponse(500, { detail: RAW }))
    expect(spy).toHaveBeenCalled()
    spy.mockRestore()
  })
})

describe('mutationErrorContent', () => {
  it('does not echo the server text for 404 or other 4xx', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    const nf = mutationErrorContent(classifyResponse(404, { detail: RAW }))
    const other = mutationErrorContent(classifyResponse(403, { detail: RAW }))
    expect(JSON.stringify(nf)).not.toContain('psycopg')
    expect(JSON.stringify(other)).not.toContain('psycopg')
    spy.mockRestore()
  })
})
