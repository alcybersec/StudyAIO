import { MemoryRouter } from 'react-router-dom'
import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '../../../hooks/useApi'
import * as spots from '../../../hooks/useWeakSpots'
import { ActivityWidget } from './ActivityWidget'
import { CoursesWidget } from './CoursesWidget'
import { DeadlinesWidget } from './DeadlinesWidget'
import { ExamsWidget } from './ExamsWidget'
import { GamificationWidget } from './GamificationWidget'
import { StreakWidget } from './StreakWidget'
import { StudyProgressWidget } from './StudyProgressWidget'
import { TonightCard } from '../../weakspots/TonightCard'
import { widgets } from '../WidgetRegistry'

vi.mock('../../../hooks/useApi', () => ({
  useDashboardActivity: vi.fn(),
  useDashboardCourses: vi.fn(),
  useDashboardDeadlines: vi.fn(),
  useDashboardExams: vi.fn(),
  useDashboardGamification: vi.fn(),
  useDashboardStreak: vi.fn(),
  useDashboardStudyStats: vi.fn(),
  useUpload: vi.fn(),
}))
vi.mock('../../../hooks/useWeakSpots', () => ({
  useTonightPlan: vi.fn(),
  useRefreshTonightPlan: vi.fn(() => ({ mutate: vi.fn(), isPending: false, isError: false })),
}))
vi.mock('../../../api/usage', () => ({ recordUsageEvent: vi.fn() }))

const result = (data: unknown) =>
  ({ data, isLoading: false, isError: false, refetch: vi.fn() }) as never

const COURSE = { id: 'c1', code: 'CSIT302', name: null, total_artifacts: 2, weeks_covered: 1 }

function mockEmpty(courses: unknown[] = []) {
  vi.mocked(api.useDashboardActivity).mockReturnValue(result([]))
  vi.mocked(api.useDashboardCourses).mockReturnValue(result(courses))
  vi.mocked(api.useDashboardDeadlines).mockReturnValue(result([]))
  vi.mocked(api.useDashboardExams).mockReturnValue(result([]))
  vi.mocked(api.useDashboardGamification).mockReturnValue(result(null))
  vi.mocked(api.useDashboardStreak).mockReturnValue(result({ current_streak: 0, longest_streak: 0, last_study_date: null }))
  vi.mocked(api.useDashboardStudyStats).mockReturnValue(result({ total: 0, per_course: [] }))
  vi.mocked(spots.useTonightPlan).mockReturnValue(
    result({ items: [], focus: [], done_count: 0, total_minutes: 0, diagnostic: null }),
  )
}

const renderIn = (ui: React.ReactNode) => render(<MemoryRouter>{ui}</MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
  mockEmpty()
})

/** Every dashboard widget that reads a query, with the call to action its empty state must carry. */
const CASES: [string, () => React.ReactNode, string, string][] = [
  ['tonight', () => <TonightCard />, 'Upload a lecture', '/upload'],
  ['streak', () => <StreakWidget />, 'Start studying', '/study'],
  ['exams', () => <ExamsWidget />, 'Go to Exams', '/study?tab=exams'],
  ['gamification', () => <GamificationWidget />, 'Start studying', '/study'],
  ['study', () => <StudyProgressWidget />, 'Upload a lecture', '/upload'],
  ['deadlines', () => <DeadlinesWidget />, 'Upload a lecture', '/upload'],
  ['activity', () => <ActivityWidget />, 'Upload a lecture', '/upload'],
  ['courses', () => <CoursesWidget />, 'Upload', '/upload'],
]

describe('empty widgets carry a call to action', () => {
  it.each(CASES)('%s', (_key, node, label, href) => {
    renderIn(node())
    expect(screen.getByRole('link', { name: label })).toHaveAttribute('href', href)
  })

  it('covers every registered widget (quick upload is itself the action)', () => {
    const covered = new Set([...CASES.map(([k]) => k), 'upload'])
    expect(widgets.map((w) => w.key).filter((k) => !covered.has(k))).toEqual([])
  })
})

describe('with an uploaded course', () => {
  beforeEach(() => mockEmpty([COURSE]))

  it('deadlines point at the course outline', () => {
    renderIn(<DeadlinesWidget />)
    expect(screen.getByRole('link', { name: 'Add a course outline' })).toHaveAttribute('href', '/courses/CSIT302/ops')
  })

  it('study tonight points at the check-in on the mastery map', () => {
    renderIn(<TonightCard />)
    expect(screen.getByRole('link', { name: 'See your mastery map' })).toHaveAttribute('href', '/study?tab=mastery')
  })
})
