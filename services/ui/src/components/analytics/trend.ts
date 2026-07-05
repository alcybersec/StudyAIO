import type { HeatmapDay } from '../../types'

/**
 * Bucket daily heatmap values into weekly sums for stat-card sparklines.
 * Returns an empty array when there is no signal (all zeros / no data),
 * so callers can hide the sparkline instead of drawing a flat line.
 */
export function weeklyTrend(
  days: HeatmapDay[] | undefined,
  pick: (day: HeatmapDay) => number,
  weeks = 8,
): number[] {
  if (!days || days.length === 0) return []
  const recent = days.slice(-weeks * 7)
  const buckets: number[] = []
  for (let i = 0; i < recent.length; i += 7) {
    buckets.push(recent.slice(i, i + 7).reduce((sum, d) => sum + pick(d), 0))
  }
  return buckets.some((v) => v > 0) ? buckets : []
}

/** Heatmap cell intensity level 0-4 from minutes studied. */
export function heatLevel(minutes: number): number {
  if (minutes <= 0) return 0
  if (minutes <= 15) return 1
  if (minutes <= 30) return 2
  if (minutes <= 60) return 3
  return 4
}

/** Opacity applied to the sage tone per intensity level (level 0 uses surface). */
export const LEVEL_OPACITY = [0, 0.25, 0.45, 0.7, 1] as const
