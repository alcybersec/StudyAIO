import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AssessmentTable } from './AssessmentTable'
import { daysUntil } from './dates'
import { DeadlineTimeline } from './DeadlineTimeline'
import { DocumentList } from './DocumentList'
import { useCreateExamFromDeadline, useDeleteDeadline, useUpdateDeadline } from '../../hooks/useApi'
import { useCalendarStatus, useSyncCalendar } from '../../hooks/useCalendar'
import type { Assessment, CourseDocument, Deadline } from '../../types'

vi.mock('../../hooks/useApi', () => ({
  useCreateExamFromDeadline: vi.fn(),
  useDeleteDeadline: vi.fn(),
  useUpdateDeadline: vi.fn(),
}))

vi.mock('../../hooks/useCalendar', () => ({
  useCalendarStatus: vi.fn(),
  useSyncCalendar: vi.fn(),
}))

const asResult = (q: object) => q as never

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(useCreateExamFromDeadline).mockReturnValue(asResult({ mutate: vi.fn(), isPending: false }))
  vi.mocked(useDeleteDeadline).mockReturnValue(asResult({ mutate: vi.fn(), isPending: false }))
  vi.mocked(useUpdateDeadline).mockReturnValue(asResult({ mutate: vi.fn(), isPending: false }))
  vi.mocked(useCalendarStatus).mockReturnValue(asResult({ data: undefined }))
  vi.mocked(useSyncCalendar).mockReturnValue(asResult({ mutate: vi.fn(), isPending: false }))
})

const makeAssessment = (overrides: Partial<Assessment> = {}): Assessment => ({
  id: 'a1',
  course_id: 'c1',
  source_document_id: null,
  title: 'Final Exam',
  assessment_type: 'exam',
  weight_pct: 60,
  description: null,
  weeks_relevant: [12, 13],
  created_at: '2026-01-01T00:00:00',
  updated_at: '2026-01-01T00:00:00',
  ...overrides,
})

const isoDaysFromNow = (days: number): string => {
  const d = new Date()
  d.setDate(d.getDate() + days)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

const makeDeadline = (overrides: Partial<Deadline> = {}): Deadline => ({
  id: 'd1',
  course_id: 'c1',
  assessment_id: null,
  source_document_id: null,
  title: 'Assignment 1',
  due_date: isoDaysFromNow(10),
  deadline_type: 'assignment',
  description: null,
  is_confirmed: false,
  created_at: '2026-01-01T00:00:00',
  updated_at: '2026-01-01T00:00:00',
  ...overrides,
})

const makeDocument = (overrides: Partial<CourseDocument> = {}): CourseDocument => ({
  id: 'doc1',
  course_id: 'c1',
  document_type: 'outline',
  title: null,
  original_filename: 'outline.pdf',
  file_type: 'pdf',
  sha256: 'abc',
  file_size_bytes: 2048,
  status: 'processed',
  created_at: '2026-01-01T00:00:00',
  updated_at: '2026-01-01T00:00:00',
  ...overrides,
})

describe('daysUntil', () => {
  // Passing `now` parsed from the same date-only format keeps the assertions
  // timezone-independent: both dates shift by the same local offset.
  const now = new Date('2026-07-15')

  it('returns 0 for today', () => {
    expect(daysUntil('2026-07-15', now)).toBe(0)
  })

  it('returns positive days for future dates', () => {
    expect(daysUntil('2026-07-18', now)).toBe(3)
  })

  it('returns negative days for past dates', () => {
    expect(daysUntil('2026-07-13', now)).toBe(-2)
  })
})

describe('AssessmentTable four states', () => {
  it('renders a skeleton while loading without data', () => {
    render(<AssessmentTable assessments={undefined} isLoading isError={false} onRetry={vi.fn()} />)
    expect(screen.getByRole('status', { name: /loading assessments/i })).toBeInTheDocument()
  })

  it('renders an ErrorState with a working retry when the query fails', async () => {
    const user = userEvent.setup()
    const onRetry = vi.fn()
    render(<AssessmentTable assessments={undefined} isLoading={false} isError onRetry={onRetry} />)

    expect(screen.getByRole('alert')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /retry/i }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('renders an EmptyState when there are no assessments', () => {
    render(<AssessmentTable assessments={[]} isLoading={false} isError={false} onRetry={vi.fn()} />)
    expect(screen.getByText(/no assessments extracted yet/i)).toBeInTheDocument()
  })

  it('keeps rendering cached data when a background refetch fails', () => {
    render(<AssessmentTable assessments={[makeAssessment()]} isLoading={false} isError onRetry={vi.fn()} />)
    expect(screen.getByText('Final Exam')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows a total row summing assessment weights', () => {
    render(
      <AssessmentTable
        assessments={[makeAssessment(), makeAssessment({ id: 'a2', title: 'Quiz 1', weight_pct: 15 })]}
        isLoading={false}
        isError={false}
        onRetry={vi.fn()}
      />,
    )
    expect(screen.getByText('Total')).toBeInTheDocument()
    expect(screen.getByText('75%')).toBeInTheDocument()
  })
})

describe('DeadlineTimeline four states', () => {
  it('renders a skeleton while loading without data', () => {
    render(<DeadlineTimeline deadlines={undefined} isLoading isError={false} onRetry={vi.fn()} />)
    expect(screen.getByRole('status', { name: /loading deadlines/i })).toBeInTheDocument()
  })

  it('renders an ErrorState with a working retry when the query fails', async () => {
    const user = userEvent.setup()
    const onRetry = vi.fn()
    render(<DeadlineTimeline deadlines={undefined} isLoading={false} isError onRetry={onRetry} />)

    expect(screen.getByRole('alert')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /retry/i }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('renders an EmptyState when there are no deadlines', () => {
    render(<DeadlineTimeline deadlines={[]} isLoading={false} isError={false} onRetry={vi.fn()} />)
    expect(screen.getByText(/no deadlines extracted yet/i)).toBeInTheDocument()
  })

  it('marks deadlines within 3 days as urgent', () => {
    render(
      <DeadlineTimeline
        deadlines={[makeDeadline({ due_date: isoDaysFromNow(2) })]}
        isLoading={false}
        isError={false}
        onRetry={vi.fn()}
      />,
    )
    expect(screen.getByText('urgent')).toBeInTheDocument()
  })

  it('confirming a deadline sends an is_confirmed update', async () => {
    const user = userEvent.setup()
    const mutate = vi.fn()
    vi.mocked(useUpdateDeadline).mockReturnValue(asResult({ mutate, isPending: false }))

    render(<DeadlineTimeline deadlines={[makeDeadline()]} isLoading={false} isError={false} onRetry={vi.fn()} />)
    await user.click(screen.getByRole('button', { name: /confirm/i }))

    expect(mutate).toHaveBeenCalledWith({ deadlineId: 'd1', data: { is_confirmed: true } })
  })
})

describe('DocumentList four states', () => {
  it('renders a skeleton while loading without data', () => {
    render(<DocumentList documents={undefined} isLoading isError={false} onRetry={vi.fn()} />)
    expect(screen.getByRole('status', { name: /loading documents/i })).toBeInTheDocument()
  })

  it('renders an ErrorState instead of silently dropping a failed query', async () => {
    const user = userEvent.setup()
    const onRetry = vi.fn()
    render(<DocumentList documents={undefined} isLoading={false} isError onRetry={onRetry} />)

    expect(screen.getByRole('alert')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /retry/i }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('renders a visible EmptyState when there are no documents', () => {
    render(<DocumentList documents={[]} isLoading={false} isError={false} onRetry={vi.fn()} />)
    expect(screen.getByText(/no documents uploaded yet/i)).toBeInTheDocument()
  })

  it('renders document rows with a status badge', () => {
    render(<DocumentList documents={[makeDocument()]} isLoading={false} isError={false} onRetry={vi.fn()} />)
    expect(screen.getByText('outline.pdf')).toBeInTheDocument()
    expect(screen.getByText(/processed/i)).toBeInTheDocument()
  })
})
