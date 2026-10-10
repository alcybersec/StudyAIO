import { calendarDayIn } from '../../lib/timezone'

/**
 * Whole days between today and a date-only string. "Today" is the calendar day
 * in `timeZone` (the user's stored zone) when given, else the browser's.
 */
export function daysUntil(dateStr: string, now: Date = new Date(), timeZone?: string): number {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(dateStr)
  const today = calendarDayIn(now, timeZone)
  const due = m
    ? new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])))
    : calendarDayIn(new Date(dateStr))
  return Math.ceil((due.getTime() - today.getTime()) / (1000 * 60 * 60 * 24))
}
