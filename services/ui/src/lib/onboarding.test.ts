import { describe, expect, it } from 'vitest'
import { deriveOnboarding, firstCourseWithMaterial, firstSummaryTarget, hasStudyEvidence } from './onboarding'
import type { CourseDetail, CourseListItem, WeakSpotsResponse } from '../types'

const base = {
  courses: [],
  recentActivity: [],
  trackedUploads: 0,
  activeUploads: 0,
  summaryTarget: null,
  summaryRead: false,
  checkInDone: false,
}
const target = { courseId: 'c1', courseCode: 'X1', week: 1 }

describe('deriveOnboarding', () => {
  it('new user', () => {
    expect(deriveOnboarding(base)).toEqual({ phase: 'new', upload: 'active', summary: 'locked', checkIn: 'locked' })
  })
  it('a session upload counts before the server has an artifact', () => {
    expect(deriveOnboarding({ ...base, trackedUploads: 1 }).phase).toBe('processing')
  })
  it('processing keeps the summary locked', () => {
    expect(deriveOnboarding({ ...base, activeUploads: 1 }).summary).toBe('locked')
  })
  it('has summary: check-in opens, summary done once read', () => {
    expect(deriveOnboarding({ ...base, summaryTarget: target })).toMatchObject({
      phase: 'has_summary',
      summary: 'active',
      checkIn: 'active',
    })
    expect(deriveOnboarding({ ...base, summaryTarget: target, summaryRead: true }).summary).toBe('done')
  })
  it('done wins over everything', () => {
    expect(deriveOnboarding({ ...base, checkInDone: true }).phase).toBe('done')
  })
})

describe('helpers', () => {
  const course = (over: Partial<CourseListItem>) =>
    ({ id: 'c', code: 'A', weeks_covered: 0, total_artifacts: 0, ...over }) as CourseListItem

  it('picks the first course with material', () => {
    expect(firstCourseWithMaterial([course({}), course({ code: 'B', total_artifacts: 1 })])?.code).toBe('B')
    expect(firstCourseWithMaterial(undefined)).toBeNull()
  })

  it('picks the lowest summarised week', () => {
    const detail = {
      course: { id: 'c', code: 'A' },
      weeks: [
        { week: 3, summary_id: 's3' },
        { week: 1, summary_id: null },
        { week: 2, summary_id: 's2' },
      ],
    } as unknown as CourseDetail
    expect(firstSummaryTarget(detail)).toEqual({ courseId: 'c', courseCode: 'A', week: 2 })
    expect(firstSummaryTarget(undefined)).toBeNull()
  })

  it('study evidence needs an answer or a review', () => {
    const resp = (quiz: number, cards: number) =>
      ({
        courses: [{ weeks: [{ evidence: { quiz_attempts: quiz, cards_reviewed: cards } }] }],
      }) as unknown as WeakSpotsResponse
    expect(hasStudyEvidence(resp(0, 0))).toBe(false)
    expect(hasStudyEvidence(resp(1, 0))).toBe(true)
    expect(hasStudyEvidence(resp(0, 2))).toBe(true)
    expect(hasStudyEvidence(undefined)).toBe(false)
  })
})
