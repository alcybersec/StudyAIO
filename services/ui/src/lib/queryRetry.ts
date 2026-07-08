import { NotFoundError, ValidationError } from '../api/errors'

/**
 * React Query retry predicate: retrying a validation failure or a missing
 * entity can never succeed, everything else (network, 5xx, unknown) gets
 * up to two retries.
 */
export function shouldRetryQuery(failureCount: number, error: unknown): boolean {
  if (error instanceof ValidationError || error instanceof NotFoundError) return false
  return failureCount < 2
}
