import type { HeatmapDay } from '../types'

/**
 * Recent study activity for the history table: days with any activity,
 * newest first, capped at `limit` rows.
 */
export function recentActivity(days: HeatmapDay[], limit = 14): HeatmapDay[] {
  return days
    .filter((day) => day.cards > 0 || day.sessions > 0 || day.minutes > 0)
    .sort((a, b) => (a.date < b.date ? 1 : -1))
    .slice(0, limit)
}
