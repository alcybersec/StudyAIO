import { useEffect, useRef } from 'react'
import { browserTimeZone, DEFAULT_TIME_ZONE, wasTimeZoneChosen } from '../lib/timezone'
import { useSettings, useUpdateSettings } from './useApi'

/** The stored zone that defines "today" for this user; undefined until loaded. */
export function useUserTimeZone(): string | undefined {
  const { data } = useSettings()
  return data?.timezone
}

/**
 * Adopt the browser's zone once, for accounts still on the default.
 *
 * Skipped when the stored zone is anything but the default, or when the user
 * ever chose a zone by hand. Fires at most once per mount (and a failed PUT is
 * not retried, so a rejecting server cannot loop).
 */
export function useAutoTimeZone(): void {
  const { data } = useSettings()
  const { mutate } = useUpdateSettings()
  const attempted = useRef(false)
  const stored = data?.timezone

  useEffect(() => {
    if (attempted.current || stored === undefined) return
    attempted.current = true
    if (stored !== DEFAULT_TIME_ZONE || wasTimeZoneChosen()) return
    const detected = browserTimeZone()
    if (!detected || detected === DEFAULT_TIME_ZONE) return
    mutate({ timezone: detected })
  }, [stored, mutate])
}
