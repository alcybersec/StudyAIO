import type { ActivityItem, CourseDetail, CourseListItem, WeakSpotsResponse } from '../types'

export type OnboardingPhase = 'new' | 'processing' | 'has_summary' | 'done'
export type StepStatus = 'done' | 'active' | 'locked'

/** The first summarised week: where step 2 links and which week the check-in is for. */
export interface SummaryTarget {
  courseId: string
  courseCode: string
  week: number
}

export interface OnboardingInputs {
  courses: CourseListItem[] | undefined
  recentActivity: ActivityItem[] | undefined
  /** Files tracked this session plus artifacts still moving through the pipeline. */
  trackedUploads: number
  activeUploads: number
  summaryTarget: SummaryTarget | null
  summaryRead: boolean
  checkInDone: boolean
}

export interface OnboardingState {
  phase: OnboardingPhase
  upload: StepStatus
  summary: StepStatus
  checkIn: StepStatus
}

/** The course the first summary is looked for in: the first one with any material. */
export function firstCourseWithMaterial(courses: CourseListItem[] | undefined): CourseListItem | null {
  return courses?.find((c) => c.weeks_covered > 0 || c.total_artifacts > 0) ?? null
}

/** First week of a course detail that has a summary, in week order. */
export function firstSummaryTarget(detail: CourseDetail | undefined): SummaryTarget | null {
  if (!detail) return null
  const week = [...detail.weeks].sort((a, b) => a.week - b.week).find((w) => !!w.summary_id)
  return week ? { courseId: detail.course.id, courseCode: detail.course.code, week: week.week } : null
}

/**
 * Any quiz answer or card review anywhere counts as having taken a check-in;
 * the user is past cold start whichever door they came through.
 */
export function hasStudyEvidence(data: WeakSpotsResponse | undefined): boolean {
  return !!data?.courses.some((c) =>
    c.weeks.some((w) => w.evidence.quiz_attempts > 0 || w.evidence.cards_reviewed > 0),
  )
}

export function deriveOnboarding(i: OnboardingInputs): OnboardingState {
  const uploaded =
    i.trackedUploads > 0 ||
    i.activeUploads > 0 ||
    (i.recentActivity?.length ?? 0) > 0 ||
    !!i.courses?.some((c) => c.total_artifacts > 0)

  if (i.checkInDone) return { phase: 'done', upload: 'done', summary: 'done', checkIn: 'done' }
  if (i.summaryTarget) {
    return {
      phase: 'has_summary',
      upload: 'done',
      summary: i.summaryRead ? 'done' : 'active',
      checkIn: 'active',
    }
  }
  if (uploaded) return { phase: 'processing', upload: 'done', summary: 'locked', checkIn: 'locked' }
  return { phase: 'new', upload: 'active', summary: 'locked', checkIn: 'locked' }
}
