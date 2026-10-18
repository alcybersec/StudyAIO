/**
 * Routing predicates for the service worker, kept free of Workbox so they can
 * be unit-tested.
 *
 * Long-lived event streams must never pass through a caching route. A Workbox
 * strategy fetches on the worker's behalf, and that fetch outlives the page
 * that asked for it, so every full page load would leave one stream open in
 * the worker until the per-host HTTP/1.1 connection limit starves every other
 * request.
 */

/** Paths that are served as a never-ending stream. */
const STREAM_PATHS = ['/api/uploads/pipeline-events']

/** True when the request is a long-lived event stream the worker must not touch. */
export function isEventStream(
  url: Pick<URL, 'pathname'>,
  request?: Pick<Request, 'headers'>
): boolean {
  if (STREAM_PATHS.some((p) => url.pathname === p || url.pathname.startsWith(`${p}/`))) {
    return true
  }
  const accept = request?.headers?.get('accept') ?? ''
  return accept.toLowerCase().includes('text/event-stream')
}

/** The general `/api/` NetworkFirst route: GETs worth caching for a short time. */
export function isGeneralApiCacheable(
  url: Pick<URL, 'pathname'>,
  request?: Pick<Request, 'headers'>
): boolean {
  return (
    url.pathname.startsWith('/api/') &&
    !isEventStream(url, request) &&
    !url.pathname.startsWith('/api/auth/') &&
    !url.pathname.startsWith('/api/study/review') &&
    !url.pathname.startsWith('/api/study/quiz-attempt')
  )
}
