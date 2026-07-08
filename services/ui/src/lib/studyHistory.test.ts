import { describe, expect, it } from 'vitest'
import { recentActivity } from './studyHistory'
import type { HeatmapDay } from '../types'

const d = (date: string, cards: number, sessions: number, minutes = 10): HeatmapDay => ({
  date,
  cards,
  sessions,
  minutes,
})

describe('recentActivity', () => {
  it('drops days with no activity', () => {
    const days = [d('2026-07-01', 0, 0, 0), d('2026-07-02', 12, 1)]
    expect(recentActivity(days).map((x) => x.date)).toEqual(['2026-07-02'])
  })

  it('sorts newest first', () => {
    const days = [d('2026-07-01', 5, 1), d('2026-07-03', 8, 2), d('2026-07-02', 3, 1)]
    expect(recentActivity(days).map((x) => x.date)).toEqual([
      '2026-07-03',
      '2026-07-02',
      '2026-07-01',
    ])
  })

  it('caps the number of rows', () => {
    const days = Array.from({ length: 20 }, (_, i) =>
      d(`2026-06-${String(i + 1).padStart(2, '0')}`, 1, 1),
    )
    expect(recentActivity(days, 14)).toHaveLength(14)
  })
})
