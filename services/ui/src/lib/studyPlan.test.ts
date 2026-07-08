import { describe, expect, it } from 'vitest'
import {
  formatPlanDayLabel,
  isPlanItemDone,
  isPlanToday,
  planCourses,
  planHasItems,
} from './studyPlan'
import type { StudyPlanDay } from '../types'

const day = (iso: string, items: StudyPlanDay['items'] = []): StudyPlanDay => ({
  day: iso,
  items,
})

describe('formatPlanDayLabel', () => {
  it('formats an ISO date as a short weekday', () => {
    // 2026-07-06 is a Monday
    expect(formatPlanDayLabel('2026-07-06')).toBe('Mon')
    expect(formatPlanDayLabel('2026-07-10')).toBe('Fri')
  })

  it('returns the raw value when the date is unparsable', () => {
    expect(formatPlanDayLabel('not-a-date')).toBe('not-a-date')
  })
})

describe('isPlanToday', () => {
  it('matches only the reference date', () => {
    const now = new Date(2026, 6, 4) // local 2026-07-04
    expect(isPlanToday('2026-07-04', now)).toBe(true)
    expect(isPlanToday('2026-07-05', now)).toBe(false)
  })
})

describe('isPlanItemDone', () => {
  it('is done when the done count reaches the target', () => {
    expect(isPlanItemDone({ course_code: 'CSIT302', kind: 'cards', target: 20, done: 20 })).toBe(true)
    expect(isPlanItemDone({ course_code: 'CSIT302', kind: 'cards', target: 20, done: 25 })).toBe(true)
  })

  it('is not done below target or when the target is zero', () => {
    expect(isPlanItemDone({ course_code: 'CSIT302', kind: 'cards', target: 20, done: 19 })).toBe(false)
    expect(isPlanItemDone({ course_code: 'CSIT302', kind: 'quiz', target: 0, done: 0 })).toBe(false)
  })
})

describe('planHasItems', () => {
  it('is false for an empty week', () => {
    expect(planHasItems([])).toBe(false)
    expect(planHasItems([day('2026-07-04'), day('2026-07-05')])).toBe(false)
  })

  it('is true when any day has an item', () => {
    expect(
      planHasItems([
        day('2026-07-04'),
        day('2026-07-05', [{ course_code: 'CSIT302', kind: 'cards', target: 10, done: 0 }]),
      ]),
    ).toBe(true)
  })
})

describe('planCourses', () => {
  it('returns distinct course codes in first-seen order', () => {
    const days = [
      day('2026-07-04', [
        { course_code: 'CSIT302', kind: 'cards' as const, target: 10, done: 0 },
        { course_code: 'CSCI368', kind: 'quiz' as const, target: 5, done: 0 },
      ]),
      day('2026-07-05', [{ course_code: 'CSIT302', kind: 'cards' as const, target: 10, done: 0 }]),
    ]
    expect(planCourses(days)).toEqual(['CSIT302', 'CSCI368'])
  })
})
