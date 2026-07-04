/**
 * Typed API error taxonomy.
 *
 * Every non-2xx response from the API client is classified into one of these
 * error classes so callers (React Query retry predicates, toast mapping,
 * form field errors) can branch on error type instead of parsing strings.
 */

export class AppApiError extends Error {
  status: number
  detail?: unknown

  constructor(msg: string, status: number, detail?: unknown) {
    super(msg)
    this.name = 'AppApiError'
    this.status = status
    this.detail = detail
  }
}

/** Request never reached the server (offline, DNS, CORS) or timed out. */
export class NetworkError extends AppApiError {
  constructor(msg = 'Network request failed', status = 0, detail?: unknown) {
    super(msg, status, detail)
    this.name = 'NetworkError'
  }
}

/** 400/422 — the request payload was rejected; `fields` maps field → message. */
export class ValidationError extends AppApiError {
  fields: Record<string, string> = {}

  constructor(msg: string, status: number, detail?: unknown) {
    super(msg, status, detail)
    this.name = 'ValidationError'
  }
}

/** 404 — the entity does not exist (or is not visible to this user). */
export class NotFoundError extends AppApiError {
  constructor(msg: string, status: number, detail?: unknown) {
    super(msg, status, detail)
    this.name = 'NotFoundError'
  }
}

/** 429 — rate limited; `retryAfterSeconds` comes from the Retry-After header. */
export class RateLimitError extends AppApiError {
  retryAfterSeconds = 30

  constructor(msg: string, status: number, detail?: unknown) {
    super(msg, status, detail)
    this.name = 'RateLimitError'
  }
}

/** 5xx — the server failed; safe to retry. */
export class ServerError extends AppApiError {
  constructor(msg: string, status: number, detail?: unknown) {
    super(msg, status, detail)
    this.name = 'ServerError'
  }
}

interface FastApiValidationItem {
  loc?: (string | number)[]
  msg?: string
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function extractDetail(body: unknown): unknown {
  return isRecord(body) && 'detail' in body ? body.detail : body
}

function extractMessage(body: unknown, fallback: string): string {
  const detail = extractDetail(body)
  return typeof detail === 'string' && detail.length > 0 ? detail : fallback
}

/** Build the field → message map from a 400/422 response body. */
function extractFields(body: unknown): Record<string, string> {
  const detail = extractDetail(body)
  const fields: Record<string, string> = {}

  // Simple map form: { detail: { email: "Invalid email" } }
  if (isRecord(detail)) {
    for (const [key, value] of Object.entries(detail)) {
      if (typeof value === 'string') fields[key] = value
    }
    return fields
  }

  // FastAPI form: { detail: [{ loc: ["body", "email"], msg: "..." }] }
  if (Array.isArray(detail)) {
    for (const item of detail as FastApiValidationItem[]) {
      const loc = item.loc?.filter((part) => part !== 'body')
      const key = loc && loc.length > 0 ? String(loc[loc.length - 1]) : ''
      if (key && item.msg) fields[key] = item.msg
    }
  }
  return fields
}

/**
 * Classify a non-2xx response into a typed error.
 *
 * @param status HTTP status code.
 * @param body Parsed JSON body (or best-effort fallback).
 * @param retryAfterSeconds Parsed Retry-After header value, when present.
 */
export function classifyResponse(
  status: number,
  body: unknown,
  retryAfterSeconds?: number,
): AppApiError {
  const detail = extractDetail(body)

  if (status === 400 || status === 422) {
    const err = new ValidationError(
      extractMessage(body, 'The request was invalid'),
      status,
      detail,
    )
    err.fields = extractFields(body)
    return err
  }

  if (status === 404) {
    return new NotFoundError(extractMessage(body, 'Not found'), status, detail)
  }

  if (status === 429) {
    const err = new RateLimitError(
      extractMessage(body, 'Too many requests — try again shortly'),
      status,
      detail,
    )
    if (typeof retryAfterSeconds === 'number' && Number.isFinite(retryAfterSeconds)) {
      err.retryAfterSeconds = retryAfterSeconds
    }
    return err
  }

  if (status >= 500) {
    return new ServerError(extractMessage(body, 'The server hit a problem'), status, detail)
  }

  return new AppApiError(extractMessage(body, `Request failed (${status})`), status, detail)
}
