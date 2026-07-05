import { describe, expect, it } from 'vitest'
import {
  approveResolution,
  confidenceTone,
  itemConfidencePct,
  itemFilename,
  itemGuess,
  itemReason,
} from './reviewUtils'
import type { ReviewItem } from '../../types'

function makeItem(overrides: Partial<ReviewItem> = {}): ReviewItem {
  return {
    id: 'r1',
    review_type: 'classification_course',
    entity_type: 'lecture_artifact',
    entity_id: 'a1',
    payload_json: {
      filename: 'lec03_widgets.pdf',
      reason: 'Classification confidence below threshold',
      suggestions: [{ value: { course: 'CSIT302', week: 3 }, confidence: 0.35 }],
    },
    suggested_values: { course_code: 'CSIT302', week: 3, title: 'Widgets' },
    status: 'pending',
    resolution_json: null,
    created_at: '2026-07-01T10:00:00Z',
    resolved_at: null,
    ...overrides,
  }
}

describe('confidenceTone', () => {
  it('is danger below 40, warning below 60, success otherwise', () => {
    expect(confidenceTone(39)).toBe('danger')
    expect(confidenceTone(40)).toBe('warning')
    expect(confidenceTone(59)).toBe('warning')
    expect(confidenceTone(60)).toBe('success')
    expect(confidenceTone(95)).toBe('success')
  })
})

describe('itemConfidencePct', () => {
  it('reads a 0-1 confidence from the first payload suggestion as a percent', () => {
    expect(itemConfidencePct(makeItem())).toBe(35)
  })

  it('accepts an already-percentage confidence', () => {
    const item = makeItem({
      payload_json: { suggestions: [{ value: {}, confidence: 72 }] },
    })
    expect(itemConfidencePct(item)).toBe(72)
  })

  it('returns null when no confidence is present', () => {
    expect(itemConfidencePct(makeItem({ payload_json: {} }))).toBeNull()
  })
})

describe('itemFilename / itemReason', () => {
  it('reads filename and reason from the payload', () => {
    expect(itemFilename(makeItem())).toBe('lec03_widgets.pdf')
    expect(itemReason(makeItem())).toBe('Classification confidence below threshold')
  })

  it('prefers original_filename and falls back to message', () => {
    const item = makeItem({
      payload_json: { original_filename: 'orig.pdf', message: 'dup detected' },
    })
    expect(itemFilename(item)).toBe('orig.pdf')
    expect(itemReason(item)).toBe('dup detected')
  })

  it('returns null when absent', () => {
    const item = makeItem({ payload_json: {} })
    expect(itemFilename(item)).toBeNull()
    expect(itemReason(item)).toBeNull()
  })
})

describe('itemGuess', () => {
  it('reads the suggested classification', () => {
    expect(itemGuess(makeItem())).toEqual({ courseCode: 'CSIT302', week: 3, title: 'Widgets' })
  })

  it('handles missing suggested values', () => {
    const item = makeItem({ suggested_values: {} })
    expect(itemGuess(item)).toEqual({ courseCode: null, week: null, title: null })
  })
})

describe('approveResolution', () => {
  it('builds a resolution from the suggested values', () => {
    expect(approveResolution(makeItem())).toEqual({
      course_code: 'CSIT302',
      week: 3,
      title: 'Widgets',
    })
  })

  it('omits missing fields and requires a course code', () => {
    expect(
      approveResolution(makeItem({ suggested_values: { course_code: 'CSCI368' } })),
    ).toEqual({ course_code: 'CSCI368' })
    expect(approveResolution(makeItem({ suggested_values: {} }))).toBeNull()
    expect(
      approveResolution(makeItem({ suggested_values: { course_code: 'UNKNOWN' } })),
    ).toBeNull()
  })
})
