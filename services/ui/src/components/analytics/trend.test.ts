import { describe, expect, it } from 'vitest'
import { heatLevel, weeklyTrend } from './trend'
import type { HeatmapDay } from '../../types'

function day(minutes: number, cards = 0): HeatmapDay {
  return { date: '2026-07-01', minutes, cards, sessions: minutes > 0 ? 1 : 0 }
}

describe('weeklyTrend', () => {
  it('sums days into weekly buckets', () => {
    const days = [...Array.from({ length: 7 }, () => day(10)), ...Array.from({ length: 7 }, () => day(20))]
    expect(weeklyTrend(days, (d) => d.minutes)).toEqual([70, 140])
  })

  it('returns empty for undefined or zero-signal data', () => {
    expect(weeklyTrend(undefined, (d) => d.minutes)).toEqual([])
    expect(weeklyTrend([], (d) => d.minutes)).toEqual([])
    expect(weeklyTrend(Array.from({ length: 14 }, () => day(0)), (d) => d.minutes)).toEqual([])
  })

  it('keeps only the most recent N weeks', () => {
    const days = Array.from({ length: 70 }, (_, i) => day(i < 7 ? 999 : 1))
    const trend = weeklyTrend(days, (d) => d.minutes, 8)
    expect(trend).toHaveLength(8)
    expect(Math.max(...trend)).toBe(7)
  })
})

describe('heatLevel', () => {
  it('maps minutes to intensity levels 0-4', () => {
    expect(heatLevel(0)).toBe(0)
    expect(heatLevel(10)).toBe(1)
    expect(heatLevel(16)).toBe(2)
    expect(heatLevel(45)).toBe(3)
    expect(heatLevel(61)).toBe(4)
  })
})
