import { describe, expect, it } from 'vitest'
import {
  NetworkError,
  NotFoundError,
  ServerError,
  ValidationError,
} from '../api/errors'
import { shouldRetryQuery } from './queryRetry'

describe('shouldRetryQuery', () => {
  it('never retries ValidationError', () => {
    expect(shouldRetryQuery(0, new ValidationError('bad', 400))).toBe(false)
  })

  it('never retries NotFoundError', () => {
    expect(shouldRetryQuery(0, new NotFoundError('missing', 404))).toBe(false)
  })

  it('retries ServerError up to 2 attempts', () => {
    const err = new ServerError('boom', 500)
    expect(shouldRetryQuery(0, err)).toBe(true)
    expect(shouldRetryQuery(1, err)).toBe(true)
    expect(shouldRetryQuery(2, err)).toBe(false)
  })

  it('retries NetworkError up to 2 attempts', () => {
    const err = new NetworkError()
    expect(shouldRetryQuery(0, err)).toBe(true)
    expect(shouldRetryQuery(2, err)).toBe(false)
  })

  it('retries unknown errors under the cap', () => {
    expect(shouldRetryQuery(0, new Error('unknown'))).toBe(true)
    expect(shouldRetryQuery(2, new Error('unknown'))).toBe(false)
  })
})
