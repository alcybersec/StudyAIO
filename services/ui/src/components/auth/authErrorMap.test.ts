import { describe, expect, it } from 'vitest'
import {
  AppApiError,
  NetworkError,
  RateLimitError,
  ValidationError,
} from '../../api/errors'
import { classifyAuthError } from './authErrorMap'

describe('classifyAuthError', () => {
  it('maps 401 to wrong credentials', () => {
    expect(classifyAuthError(new AppApiError('Invalid credentials', 401))).toEqual({
      kind: 'credentials',
    })
  })

  it('maps a 403 MFA challenge to mfa_required', () => {
    expect(classifyAuthError(new AppApiError('MFA code required', 403))).toEqual({
      kind: 'mfa_required',
    })
  })

  it('maps a plain 403 to a generic message, not MFA', () => {
    expect(classifyAuthError(new AppApiError('Forbidden', 403))).toEqual({
      kind: 'other',
      message: 'Forbidden',
    })
  })

  it('maps ValidationError to field errors', () => {
    const err = new ValidationError('Invalid payload', 422)
    err.fields = { email: 'Enter a valid email address' }
    expect(classifyAuthError(err)).toEqual({
      kind: 'fields',
      fields: { email: 'Enter a valid email address' },
      message: 'Invalid payload',
    })
  })

  it('maps RateLimitError to a cooldown with the Retry-After value', () => {
    const err = new RateLimitError('Too many requests', 429)
    err.retryAfterSeconds = 42
    expect(classifyAuthError(err)).toEqual({ kind: 'rate_limited', retryAfterSeconds: 42 })
  })

  it('maps NetworkError to network', () => {
    expect(classifyAuthError(new NetworkError())).toEqual({ kind: 'network' })
  })

  it('maps 409 to conflict', () => {
    expect(classifyAuthError(new AppApiError('User already exists', 409))).toEqual({
      kind: 'conflict',
      message: 'User already exists',
    })
  })

  it('maps unknown errors to other', () => {
    expect(classifyAuthError(new Error('boom'))).toEqual({ kind: 'other', message: 'boom' })
  })
})
