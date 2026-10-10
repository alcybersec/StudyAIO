/** Per-user time zone helpers (R-023: the stored IANA zone defines "today"). */

export const DEFAULT_TIME_ZONE = 'UTC'
export const TIMEZONE_CHOSEN_KEY = 'studyaio-timezone-chosen'

const FALLBACK_ZONES = [
  'UTC',
  'Europe/London',
  'Europe/Berlin',
  'Europe/Paris',
  'Europe/Moscow',
  'Europe/Istanbul',
  'Asia/Dubai',
  'Asia/Kolkata',
  'Asia/Singapore',
  'Asia/Shanghai',
  'Asia/Tokyo',
  'Australia/Sydney',
  'Pacific/Auckland',
  'America/Sao_Paulo',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'Africa/Cairo',
  'Africa/Johannesburg',
]

/** The browser's IANA zone, or null when it cannot be determined. */
export function browserTimeZone(): string | null {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || null
  } catch {
    return null
  }
}

/** Every zone the runtime knows, with a short fallback list for older engines. */
export function listTimeZones(): string[] {
  try {
    const supported = (
      Intl as unknown as { supportedValuesOf?: (key: string) => string[] }
    ).supportedValuesOf?.('timeZone')
    if (supported && supported.length > 0) {
      return supported.includes('UTC') ? supported : ['UTC', ...supported]
    }
  } catch {
    /* fall through */
  }
  return FALLBACK_ZONES
}

export function isValidTimeZone(zone: string): boolean {
  try {
    new Intl.DateTimeFormat('en-US', { timeZone: zone })
    return true
  } catch {
    return false
  }
}

/** Whether the user picked a zone by hand (so auto-detect must not touch it). */
export function wasTimeZoneChosen(): boolean {
  try {
    return localStorage.getItem(TIMEZONE_CHOSEN_KEY) === '1'
  } catch {
    return false
  }
}

export function markTimeZoneChosen(): void {
  try {
    localStorage.setItem(TIMEZONE_CHOSEN_KEY, '1')
  } catch {
    /* private mode, or storage disabled */
  }
}

/**
 * The calendar day `now` falls on in `timeZone`, as a UTC-midnight Date so day
 * arithmetic is DST-proof. Falls back to the browser's local day when the zone
 * is absent or invalid.
 */
export function calendarDayIn(now: Date, timeZone?: string | null): Date {
  if (timeZone && isValidTimeZone(timeZone)) {
    const parts = new Intl.DateTimeFormat('en-CA', {
      timeZone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).formatToParts(now)
    const get = (type: string) => Number(parts.find((p) => p.type === type)?.value)
    return new Date(Date.UTC(get('year'), get('month') - 1, get('day')))
  }
  return new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()))
}
