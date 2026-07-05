import { describe, expect, it } from 'vitest'
import { daysUntil, deadlineToneClass } from './format'

describe('daysUntil', () => {
  const now = new Date('2026-07-04T00:00:00Z').getTime()

  it('counts whole days remaining', () => {
    expect(daysUntil('2026-07-09T00:00:00Z', now)).toBe(5)
  })

  it('returns 0 for the same instant', () => {
    expect(daysUntil('2026-07-04T00:00:00Z', now)).toBe(0)
  })

  it('goes negative for past deadlines', () => {
    expect(daysUntil('2026-07-01T00:00:00Z', now)).toBe(-3)
  })
})

describe('deadlineToneClass', () => {
  it('is red at 3 days or fewer', () => {
    expect(deadlineToneClass(0)).toBe('text-red-fg')
    expect(deadlineToneClass(3)).toBe('text-red-fg')
  })

  it('is amber between 4 and 7 days', () => {
    expect(deadlineToneClass(4)).toBe('text-amber-fg')
    expect(deadlineToneClass(7)).toBe('text-amber-fg')
  })

  it('is faint beyond a week', () => {
    expect(deadlineToneClass(8)).toBe('text-text-faint')
  })
})
