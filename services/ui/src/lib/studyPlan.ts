import type { StudyPlanDay, StudyPlanItem } from '../types'

/** Parse a plan day's ISO date (YYYY-MM-DD) as a local date, or null. */
function parsePlanDate(iso: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso)
  if (!match) return null
  const [, y, m, d] = match
  return new Date(Number(y), Number(m) - 1, Number(d))
}

/** Short weekday label ("Mon") for a plan day; falls back to the raw value. */
export function formatPlanDayLabel(iso: string): string {
  const date = parsePlanDate(iso)
  if (!date) return iso
  return date.toLocaleDateString('en-US', { weekday: 'short' })
}

/** Whether a plan day is today (local time). */
export function isPlanToday(iso: string, now: Date = new Date()): boolean {
  const date = parsePlanDate(iso)
  if (!date) return false
  return (
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()
  )
}

/** A plan item counts as done once its done count reaches a non-zero target. */
export function isPlanItemDone(item: StudyPlanItem): boolean {
  return item.target > 0 && item.done >= item.target
}

/** Whether any day in the plan has at least one scheduled item. */
export function planHasItems(days: StudyPlanDay[]): boolean {
  return days.some((day) => day.items.length > 0)
}

/** Distinct course codes across the plan, in first-seen order. */
export function planCourses(days: StudyPlanDay[]): string[] {
  const seen: string[] = []
  for (const day of days) {
    for (const item of day.items) {
      if (!seen.includes(item.course_code)) seen.push(item.course_code)
    }
  }
  return seen
}
