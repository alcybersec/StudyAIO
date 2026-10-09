import { describe, expect, it } from 'vitest'
import { calendarDayIn } from './timezone'
import { daysUntil } from '../components/courseops/dates'
import { isPlanToday } from './studyPlan'

// 2026-10-09 23:30 UTC is already Oct 10 in Tokyo and still Oct 9 in New York.
const NOW = new Date('2026-10-09T23:30:00Z')

describe('calendarDayIn', () => {
  it('resolves the day in the given zone', () => {
    expect(calendarDayIn(NOW, 'Asia/Tokyo').toISOString().slice(0, 10)).toBe('2026-10-10')
    expect(calendarDayIn(NOW, 'America/New_York').toISOString().slice(0, 10)).toBe('2026-10-09')
  })
})

describe('zone-aware day helpers', () => {
  it('daysUntil counts from the zone calendar day', () => {
    expect(daysUntil('2026-10-10', NOW, 'Asia/Tokyo')).toBe(0)
    expect(daysUntil('2026-10-10', NOW, 'America/New_York')).toBe(1)
  })

  it('isPlanToday follows the zone', () => {
    expect(isPlanToday('2026-10-10', NOW, 'Asia/Tokyo')).toBe(true)
    expect(isPlanToday('2026-10-10', NOW, 'America/New_York')).toBe(false)
  })
})
