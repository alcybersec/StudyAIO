import i18n from '../i18n'
import { AppApiError, NetworkError, RateLimitError, ValidationError } from '../api/errors'

/**
 * Raw error text (server `detail`, exception messages, stacks) is for
 * developers. It goes to the console in dev builds and nowhere else.
 */
export function logRawError(err: unknown): void {
  if (import.meta.env.DEV) console.error('[error]', err)
}

/**
 * Map any thrown value to a message that is safe to show a user.
 *
 * Field-level 400/422 messages are written for users and are kept; every
 * other server string is replaced by a translated message keyed on the
 * status code. Exception class names, stacks and raw detail never reach the UI.
 */
export function userErrorMessage(err: unknown, fallback?: string): string {
  logRawError(err)
  const generic = fallback ?? i18n.t('Something went wrong')
  if (err instanceof NetworkError) return i18n.t("Couldn't reach the server")
  if (err instanceof RateLimitError) {
    return i18n.t('Rate limited — try again in {{seconds}}s', { seconds: err.retryAfterSeconds })
  }
  if (err instanceof ValidationError) {
    const first = Object.values(err.fields)[0]
    return first ?? i18n.t('The request was invalid')
  }
  if (err instanceof AppApiError) {
    switch (err.status) {
      case 401:
        return i18n.t('Please sign in again.')
      case 402:
        return i18n.t('This is over your plan limit.')
      case 403:
        return i18n.t("You don't have permission to do that.")
      case 404:
        return i18n.t('It may have been removed — this item no longer exists.')
      case 409:
        return i18n.t('That conflicts with something that already exists.')
      case 413:
        return i18n.t('That file is too large.')
      default:
        return err.status >= 500 ? i18n.t('The server hit a problem') : generic
    }
  }
  return generic
}
