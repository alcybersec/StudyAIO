/**
 * Frontend error monitoring via Sentry.
 *
 * Inert unless `VITE_SENTRY_DSN` is set at build time. The SDK is loaded
 * through a dynamic import so it lands in its own chunk and never touches the
 * main bundle for installs that don't use it.
 *
 * Nothing here may throw — monitoring that breaks the app is worse than none.
 */

type SentryModule = typeof import('@sentry/react')

let sentry: SentryModule | null = null
let initPromise: Promise<boolean> | null = null

/** Query params that carry a bearer credential in reset/verification links. */
const SCRUB_PARAMS = ['token', 'access_token', 'refresh_token', 'invite_code', 'code']

const FILTERED = '[Filtered]'

/** Strip credential-bearing query params out of a URL. */
export function scrubUrl(url: string): string {
  try {
    const parsed = new URL(url, window.location.origin)
    let touched = false
    for (const param of SCRUB_PARAMS) {
      if (parsed.searchParams.has(param)) {
        parsed.searchParams.set(param, FILTERED)
        touched = true
      }
    }
    return touched ? parsed.toString() : url
  } catch {
    return url
  }
}

/**
 * Initialize Sentry if a DSN is configured.
 *
 * @returns true if Sentry was initialized, false if disabled or unavailable.
 */
export function initMonitoring(): Promise<boolean> {
  if (initPromise) return initPromise

  const dsn = (import.meta.env.VITE_SENTRY_DSN || '').trim()
  if (!dsn) {
    initPromise = Promise.resolve(false)
    return initPromise
  }

  initPromise = import('@sentry/react')
    .then((mod) => {
      mod.init({
        dsn,
        environment: import.meta.env.VITE_SENTRY_ENVIRONMENT || 'development',
        release: import.meta.env.VITE_SENTRY_RELEASE || undefined,
        // Never attach request bodies, headers or user identity automatically.
        sendDefaultPii: false,
        tracesSampleRate: Number(import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE ?? 0) || 0,
        beforeSend(event) {
          if (event.request?.url) {
            event.request.url = scrubUrl(event.request.url)
          }
          return event
        },
      })
      mod.setTag('component', 'ui')
      sentry = mod
      return true
    })
    .catch(() => {
      // Package missing or blocked (ad blockers routinely block Sentry).
      return false
    })

  return initPromise
}

/**
 * Report an error. A no-op when monitoring is disabled.
 *
 * @param error The error to report.
 * @param context Extra non-sensitive context to attach.
 */
export function captureError(error: unknown, context?: Record<string, unknown>): void {
  try {
    sentry?.captureException(error, context ? { extra: context } : undefined)
  } catch {
    // Never let reporting an error cause another one.
  }
}

/** Test seam: reset module state between tests. */
export function __resetMonitoringForTests(): void {
  sentry = null
  initPromise = null
}
