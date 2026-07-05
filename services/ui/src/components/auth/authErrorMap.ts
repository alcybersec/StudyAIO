import { AppApiError, NetworkError, RateLimitError, ValidationError } from '../../api/errors'

/**
 * Auth-flow error taxonomy mapping. Turns a thrown API error into a
 * discriminated outcome the auth pages can render without string parsing:
 * field errors, wrong-credentials, MFA challenge, rate-limit cooldown,
 * network failure, or a generic message.
 */
export type AuthErrorOutcome =
  | { kind: 'fields'; fields: Record<string, string>; message: string }
  | { kind: 'credentials' }
  | { kind: 'mfa_required' }
  | { kind: 'rate_limited'; retryAfterSeconds: number }
  | { kind: 'network' }
  | { kind: 'conflict'; message: string }
  | { kind: 'other'; message: string }

export function classifyAuthError(err: unknown): AuthErrorOutcome {
  if (err instanceof RateLimitError) {
    return { kind: 'rate_limited', retryAfterSeconds: err.retryAfterSeconds }
  }
  if (err instanceof ValidationError) {
    return { kind: 'fields', fields: err.fields, message: err.message }
  }
  if (err instanceof NetworkError) {
    return { kind: 'network' }
  }
  if (err instanceof AppApiError) {
    if (err.status === 401) return { kind: 'credentials' }
    if (err.status === 403 && err.message.toLowerCase().includes('mfa')) {
      return { kind: 'mfa_required' }
    }
    if (err.status === 409) return { kind: 'conflict', message: err.message }
    return { kind: 'other', message: err.message }
  }
  return { kind: 'other', message: err instanceof Error ? err.message : 'Something went wrong' }
}
