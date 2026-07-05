import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { ReadinessDrilldown } from './ReadinessDrilldown'
import { accuracyToneVar, isWeakTopic } from './readiness'
import type { Course, Exam, ReadinessDetail } from '../../types'

const mocks = vi.hoisted(() => ({
  useExams: vi.fn(),
  useExamReadiness: vi.fn(),
  useCourses: vi.fn(),
}))

vi.mock('../../hooks/useApi', () => ({
  useExams: mocks.useExams,
  useExamReadiness: mocks.useExamReadiness,
  useCourses: mocks.useCourses,
}))

const exam: Exam = {
  id: 'exam-1',
  course_id: 'course-1',
  title: 'CSIT302 Final',
  exam_date: new Date(Date.now() + 9 * 86400000).toISOString(),
  weeks_scope: [4, 5, 7],
  target_mastery_pct: 80,
  status: 'active',
  created_at: '',
  updated_at: '',
}

const course = { id: 'course-1', code: 'CSIT302', name: null, term: null, created_at: '', updated_at: '' } satisfies Course

const readiness: ReadinessDetail = {
  exam_id: 'exam-1',
  title: 'CSIT302 Final',
  overall: 68,
  topics: [
    { topic: 'Buffer overflows', week: 4, accuracy: 55, weight: 15, card_count: 12 },
    { topic: 'SQL injection', week: 5, accuracy: 65, weight: 5, card_count: 9 },
    { topic: 'Stack canaries', week: 7, accuracy: 88, weight: 0, card_count: 14 },
    { topic: 'Week 9', week: 9, accuracy: null, weight: 100, card_count: 0 },
  ],
}

function setup(overrides?: {
  exams?: Partial<ReturnType<typeof queryResult>>
  detail?: Partial<ReturnType<typeof queryResult>>
}) {
  mocks.useExams.mockReturnValue({ ...queryResult([exam]), ...overrides?.exams })
  mocks.useExamReadiness.mockReturnValue({ ...queryResult(readiness), ...overrides?.detail })
  mocks.useCourses.mockReturnValue(queryResult([course]))
  return render(
    <MemoryRouter>
      <ReadinessDrilldown />
    </MemoryRouter>,
  )
}

function queryResult<T>(data: T) {
  return { data, isLoading: false, error: null as Error | null, refetch: vi.fn() }
}

describe('accuracy classification thresholds', () => {
  it('classifies below 60 as red', () => {
    expect(accuracyToneVar(0)).toBe('var(--t-red)')
    expect(accuracyToneVar(59.9)).toBe('var(--t-red)')
  })

  it('classifies 60-69 as amber', () => {
    expect(accuracyToneVar(60)).toBe('var(--t-amber)')
    expect(accuracyToneVar(69.9)).toBe('var(--t-amber)')
  })

  it('classifies 70+ as sage', () => {
    expect(accuracyToneVar(70)).toBe('var(--t-sage)')
    expect(accuracyToneVar(100)).toBe('var(--t-sage)')
  })

  it('treats below-70 and unstudied topics as weak', () => {
    expect(isWeakTopic(55)).toBe(true)
    expect(isWeakTopic(69.9)).toBe(true)
    expect(isWeakTopic(70)).toBe(false)
    expect(isWeakTopic(null)).toBe(true)
  })
})

describe('ReadinessDrilldown', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders per-topic rows with threshold-toned accuracy bars', () => {
    setup()

    const rows = screen.getAllByRole('row')
    expect(rows.length).toBeGreaterThanOrEqual(4)

    const bar = (topic: string) =>
      screen.getByTestId(`accuracy-bar-${topic}`).style.background

    expect(bar('Buffer overflows')).toContain('--t-red')
    expect(bar('SQL injection')).toContain('--t-amber')
    expect(bar('Stack canaries')).toContain('--t-sage')
  })

  it('links "Study now" only on weak rows, scoped to course and week', () => {
    setup()

    const links = screen.getAllByRole('link', { name: /study now/i })
    // Weak rows: 55%, 65%, and the unstudied week — not the 88% row.
    expect(links).toHaveLength(3)
    const hrefs = links.map((l) => l.getAttribute('href'))
    expect(hrefs).toContain('/study?tab=flashcards&course=CSIT302&week=4')
    expect(hrefs).toContain('/study?tab=flashcards&course=CSIT302&week=5')
    expect(hrefs).toContain('/study?tab=flashcards&course=CSIT302&week=9')
    expect(hrefs).not.toContain('/study?tab=flashcards&course=CSIT302&week=7')
  })

  it('shows the overall readiness percentage', () => {
    setup()
    expect(screen.getByText(/68%/)).toBeInTheDocument()
  })

  it('shows an empty state when there are no active exams', () => {
    setup({ exams: { data: [] }, detail: { data: undefined } })
    expect(screen.getByText(/no active exams/i)).toBeInTheDocument()
  })

  it('shows an error state with retry when the readiness query fails', () => {
    setup({ detail: { data: undefined, error: new Error('boom') } })
    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })
})
