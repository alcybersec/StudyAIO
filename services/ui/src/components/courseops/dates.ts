/** Whole days between `now` and a date-only string, floored to local midnights. */
export function daysUntil(dateStr: string, now: Date = new Date()): number {
  const today = new Date(now)
  today.setHours(0, 0, 0, 0)
  const due = new Date(dateStr)
  due.setHours(0, 0, 0, 0)
  return Math.ceil((due.getTime() - today.getTime()) / (1000 * 60 * 60 * 24))
}
