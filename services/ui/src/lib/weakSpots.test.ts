import { describe, expect, it } from 'vitest'
import { AppApiError, RateLimitError, classifyResponse } from '../api/errors'
import {
  MASTERY_CELL_CLASS,
  dailyCapMessage,
  groupPlanItems,
  isDailyCapError,
  masteryState,
  nextUtcMidnight,
  planIsEmpty,
  runnableIds,
} from './weakSpots'
import type { TonightItem, TonightPlan } from '../types'

const item = (over: Partial<TonightItem>): TonightItem => ({
  item_type: 'card',
  item_id: 'i1',
  course_id: 'c1',
  course_code: 'CSIT302',
  week: 3,
  reason: 'review',
  minutes: 2,
  done: false,
  ...over,
})

const plan = (items: TonightItem[], over: Partial<TonightPlan> = {}): TonightPlan => ({
  plan_date: '2026-10-15',
  minutes: 25,
  version: 1,
  algorithm_version: 1,
  built_at: '2026-10-15T18:00:00Z',
  total_minutes: items.reduce((n, i) => n + i.minutes, 0),
  done_count: items.filter((i) => i.done).length,
  items,
  focus: [],
  diagnostic: null,
  ...over,
})

describe('masteryState', () => {
  it('maps the contract statuses to the four heatmap states', () => {
    expect(masteryState('unknown')).toBe('unknown')
    expect(masteryState('weak')).toBe('weak')
    expect(masteryState('shaky')).toBe('ok')
    expect(masteryState('ok')).toBe('ok')
    expect(masteryState('solid')).toBe('solid')
  })

  it('treats anything unrecognised as unknown, never weak', () => {
    expect(masteryState('mystery')).toBe('unknown')
    expect(masteryState(null)).toBe('unknown')
    expect(masteryState(undefined)).toBe('unknown')
  })

  it('never paints unknown red; only weak is red', () => {
    expect(MASTERY_CELL_CLASS.unknown).not.toMatch(/red/)
    expect(MASTERY_CELL_CLASS.ok).not.toMatch(/red/)
    expect(MASTERY_CELL_CLASS.solid).not.toMatch(/red/)
    expect(MASTERY_CELL_CLASS.weak).toMatch(/red/)
  })
})

describe('plan helpers', () => {
  it('groups items by course and week and sums their minutes', () => {
    const groups = groupPlanItems([
      item({ item_id: 'a' }),
      item({ item_id: 'b', item_type: 'quiz', minutes: 3, reason: 'targeted', done: true }),
      item({ item_id: 'c', week: 5 }),
    ])
    expect(groups).toHaveLength(2)
    expect(groups[0]).toMatchObject({ week: 3, cards: 1, quizzes: 1, minutes: 5, done: 1, total: 2, targeted: true })
    expect(groups[1]).toMatchObject({ week: 5, cards: 1, targeted: false })
  })

  it('runs only the items that are not done, split by type', () => {
    const ids = runnableIds(
      plan([
        item({ item_id: 'a' }),
        item({ item_id: 'b', done: true }),
        item({ item_id: 'q', item_type: 'quiz' }),
      ]),
    )
    expect(ids).toEqual({ cardIds: ['a'], quizIds: ['q'] })
  })

  it('is empty only with no items and no diagnostic', () => {
    expect(planIsEmpty(plan([]))).toBe(true)
    expect(planIsEmpty(plan([item({})]))).toBe(false)
    expect(planIsEmpty(plan([], { diagnostic: { course_id: 'c1', course_code: 'X', week: 1 } }))).toBe(false)
  })
})

describe('daily cap', () => {
  it('resets at the next UTC midnight', () => {
    expect(nextUtcMidnight(new Date('2026-10-15T23:30:00Z')).toISOString()).toBe('2026-10-16T00:00:00.000Z')
    expect(nextUtcMidnight(new Date('2026-12-31T01:00:00Z')).toISOString()).toBe('2027-01-01T00:00:00.000Z')
  })

  it('names the reset in the message', () => {
    expect(dailyCapMessage(new Date('2026-10-15T10:00:00Z'))).toMatch(/00:00 UTC/)
  })

  it('recognises the 429 code at the top of the body or inside detail', () => {
    const top = classifyResponse(429, { code: 'targeted_daily_cap', detail: 'cap' })
    const nested = classifyResponse(429, { detail: { code: 'targeted_daily_cap' } })
    expect(top).toBeInstanceOf(RateLimitError)
    expect(isDailyCapError(top)).toBe(true)
    expect(isDailyCapError(nested)).toBe(true)
    expect(isDailyCapError(classifyResponse(429, { detail: 'slow down' }))).toBe(false)
    expect(isDailyCapError(new AppApiError('x', 500))).toBe(false)
  })
})
