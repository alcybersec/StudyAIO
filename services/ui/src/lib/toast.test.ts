import { describe, expect, it } from 'vitest'
import {
  AppApiError,
  NetworkError,
  NotFoundError,
  RateLimitError,
  ServerError,
  ValidationError,
} from '../api/errors'
import { mutationErrorContent } from './toast'

describe('mutationErrorContent', () => {
  it('maps ValidationError to a field-check message', () => {
    const err = new ValidationError('Title is required', 400)
    err.fields = { title: 'Title is required' }
    const content = mutationErrorContent(err)
    expect(content.message).toMatch(/title is required/i)
  })

  it('maps NotFoundError to a plain not-found message', () => {
    const content = mutationErrorContent(new NotFoundError('Exam not found', 404))
    expect(content.message).toBe('Exam not found')
    expect(content.description).toMatch(/no longer exists|removed/i)
  })

  it('maps RateLimitError to a countdown message with seconds', () => {
    const err = new RateLimitError('Rate limit exceeded', 429)
    err.retryAfterSeconds = 42
    const content = mutationErrorContent(err)
    expect(content.message).toMatch(/try again in 42s/i)
  })

  it('maps NetworkError to a connectivity message', () => {
    const content = mutationErrorContent(new NetworkError())
    expect(content.message).toMatch(/couldn't reach|offline|connection/i)
  })

  it('maps ServerError to a retryable server message', () => {
    const content = mutationErrorContent(new ServerError('Internal Server Error', 500))
    expect(content.message).toMatch(/server/i)
    expect(content.description).toMatch(/retry/i)
  })

  it('uses the API message for other AppApiErrors', () => {
    const content = mutationErrorContent(new AppApiError('Quota exceeded', 402))
    expect(content.message).toBe('Quota exceeded')
  })

  it('falls back to a generic message for unknown errors', () => {
    const content = mutationErrorContent(new Error('splat'))
    expect(content.message).toMatch(/something went wrong/i)
  })
})
