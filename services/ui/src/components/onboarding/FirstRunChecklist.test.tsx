import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { FirstRunChecklist } from './FirstRunChecklist'
import { AuthContext, type AuthContextValue } from '../../contexts/AuthContext'
import { ConsentContext } from '../../contexts/consentContext'
import { PipelineEventsContext, type PipelineEventsValue } from '../../contexts/pipelineProgress'
import { onboardingKey, resetOnboardingMemory } from '../../hooks/useOnboardingState'
import { coursesApi, dashboardApi } from '../../api/endpoints'
import { weakSpotsApi } from '../../api/weakSpots'
import type { AuthUser, CourseDetail, CourseListItem, DashboardData, WeakSpotsResponse } from '../../types'

vi.mock('../../api/endpoints', async (orig) => ({
  ...(await orig<typeof import('../../api/endpoints')>()),
  dashboardApi: { get: vi.fn() },
  coursesApi: { detail: vi.fn() },
}))
vi.mock('../../api/weakSpots', () => ({
  weakSpotsApi: { list: vi.fn(), diagnostic: vi.fn() },
}))

const dashboardGet = vi.mocked(dashboardApi.get)
const courseDetail = vi.mocked(coursesApi.detail)
const spotsList = vi.mocked(weakSpotsApi.list)
const diagnostic = vi.mocked(weakSpotsApi.diagnostic)

const USER = { id: 'u1', ai_consent_required: false } as AuthUser

const COURSE: CourseListItem = {
  id: 'c1',
  code: 'CSIT302',
  name: 'Databases',
  term: null,
  created_at: '',
  updated_at: '',
  weeks_covered: 1,
  total_artifacts: 1,
  last_updated: null,
}

const dashboard = (over: Partial<DashboardData> = {}): DashboardData =>
  ({
    pending_review_count: 0,
    recent_activity: [],
    courses: [],
    study_stats: null,
    active_exams: [],
    streak: null,
    upcoming_deadlines: [],
    gamification: null,
    ...over,
  }) as DashboardData

const detailWithSummary = (summaryId: string | null): CourseDetail => ({
  course: COURSE,
  weeks: [
    { week: 2, titles: [], artifact_count: 1, summary_status: 'done', summary_id: summaryId, flashcard_count: 0, quiz_count: 0 },
  ],
})

const spots = (quizAttempts: number): WeakSpotsResponse => ({
  local_date: '2026-10-15',
  courses: [
    {
      course_id: 'c1',
      course_code: 'CSIT302',
      weeks: [
        {
          week: 2,
          status: 'unknown',
          weakness: null,
          confidence: 0,
          urgency: 0,
          priority: 0,
          evidence: { quiz_attempts: quizAttempts, quiz_accuracy: null, cards_reviewed: 0, avg_ease: null, lapsed_cards: 0, overdue_cards: 0 },
          next_exam: null,
        },
      ],
    },
  ],
})

const pipeline = (over: Partial<PipelineEventsValue> = {}): PipelineEventsValue => ({
  events: [],
  connectionState: 'open' as PipelineEventsValue['connectionState'],
  uploads: [],
  activeCount: 0,
  track: vi.fn(),
  ...over,
})

function Probe() {
  const loc = useLocation()
  return <pre data-testid="loc">{JSON.stringify({ path: loc.pathname + loc.search, state: loc.state })}</pre>
}

const requestConsent = vi.fn()

function renderChecklist(opts: { user?: AuthUser; pipe?: PipelineEventsValue } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const auth = { user: opts.user ?? USER } as unknown as AuthContextValue
  return render(
    <QueryClientProvider client={client}>
      <AuthContext.Provider value={auth}>
        <ConsentContext.Provider value={{ requestConsent }}>
          <PipelineEventsContext.Provider value={opts.pipe ?? pipeline()}>
            <MemoryRouter initialEntries={['/']}>
              <Routes>
                <Route path="/" element={<FirstRunChecklist />} />
                <Route path="*" element={<Probe />} />
              </Routes>
            </MemoryRouter>
          </PipelineEventsContext.Provider>
        </ConsentContext.Provider>
      </AuthContext.Provider>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  resetOnboardingMemory()
  spotsList.mockResolvedValue(spots(0))
  courseDetail.mockResolvedValue(detailWithSummary(null))
})

describe('visibility by state', () => {
  it('new user: upload is the active step, the rest are locked', async () => {
    dashboardGet.mockResolvedValue(dashboard())
    renderChecklist()
    const list = await screen.findByRole('list')
    const items = within(list).getAllByRole('listitem')
    expect(items).toHaveLength(3)
    expect(items[0]).toHaveAttribute('aria-current', 'step')
    expect(items[1]).toHaveAttribute('data-status', 'locked')
    expect(items[2]).toHaveAttribute('data-status', 'locked')
    expect(screen.getByRole('link', { name: 'Upload a lecture' })).toHaveAttribute('href', '/upload')
    expect(screen.queryByRole('link', { name: 'Open summary' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Start the check-in' })).not.toBeInTheDocument()
  })

  it('processing: upload is done, shows live pipeline progress, summary still locked', async () => {
    dashboardGet.mockResolvedValue(dashboard({ courses: [COURSE] }))
    renderChecklist({
      pipe: pipeline({
        activeCount: 1,
        uploads: [{ key: 'k', name: 'a.pdf', sizeBytes: 1, artifactId: 'a1' }],
        events: [{ artifact_id: 'a1', stage: 'extract', status: 'running', message: null }],
      }),
    })
    expect(await screen.findByRole('status')).toHaveTextContent('Processing your lecture: stage 3 of 6')
    const items = screen.getAllByRole('listitem')
    expect(items[0]).toHaveAttribute('data-status', 'done')
    expect(items[1]).toHaveAttribute('data-status', 'locked')
  })

  it('has a summary: links to it and enables the check-in', async () => {
    dashboardGet.mockResolvedValue(dashboard({ courses: [COURSE] }))
    courseDetail.mockResolvedValue(detailWithSummary('s1'))
    renderChecklist()
    const link = await screen.findByRole('link', { name: 'Open summary' })
    expect(link).toHaveAttribute('href', '/courses/CSIT302/weeks/2')
    expect(screen.getByRole('button', { name: 'Start the check-in' })).toBeEnabled()
    expect(screen.getAllByRole('listitem')[0]).toHaveAttribute('data-status', 'done')
  })

  it('done: renders nothing once a check-in has been answered', async () => {
    dashboardGet.mockResolvedValue(dashboard({ courses: [COURSE] }))
    courseDetail.mockResolvedValue(detailWithSummary('s1'))
    spotsList.mockResolvedValue(spots(3))
    renderChecklist()
    await waitFor(() => expect(spotsList).toHaveBeenCalled())
    await new Promise((r) => setTimeout(r, 20))
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })

  it('reading the summary marks step 2 done', async () => {
    dashboardGet.mockResolvedValue(dashboard({ courses: [COURSE] }))
    courseDetail.mockResolvedValue(detailWithSummary('s1'))
    renderChecklist()
    await userEvent.click(await screen.findByRole('link', { name: 'Open summary' }))
    expect(JSON.parse(localStorage.getItem(onboardingKey('u1')) ?? '{}').summaryRead).toBe(true)
  })
})

describe('check-in step', () => {
  it('starts the diagnostic for the summarised week and hands it to the study runner', async () => {
    dashboardGet.mockResolvedValue(dashboard({ courses: [COURSE] }))
    courseDetail.mockResolvedValue(detailWithSummary('s1'))
    diagnostic.mockResolvedValue({ course_id: 'c1', week: 2, question_ids: ['q1', 'q2'], needs_generation: false })
    renderChecklist()
    await userEvent.click(await screen.findByRole('button', { name: 'Start the check-in' }))
    const probe = JSON.parse((await screen.findByTestId('loc')).textContent ?? '{}')
    expect(diagnostic).toHaveBeenCalledWith('c1', 2)
    expect(probe.path).toBe('/study?tab=timed')
    expect(probe.state.planRun).toMatchObject({ quizIds: ['q1', 'q2'], courseCodes: ['CSIT302'] })
  })

  it('says so when the week has no questions yet instead of navigating', async () => {
    dashboardGet.mockResolvedValue(dashboard({ courses: [COURSE] }))
    courseDetail.mockResolvedValue(detailWithSummary('s1'))
    diagnostic.mockResolvedValue({ course_id: 'c1', week: 2, question_ids: [], needs_generation: true })
    renderChecklist()
    await userEvent.click(await screen.findByRole('button', { name: 'Start the check-in' }))
    expect(await screen.findByText(/no questions yet/i)).toBeInTheDocument()
    expect(screen.queryByTestId('loc')).not.toBeInTheDocument()
  })
})

describe('dismissal', () => {
  it('hides the checklist and persists per user', async () => {
    dashboardGet.mockResolvedValue(dashboard())
    renderChecklist()
    await userEvent.click(await screen.findByRole('button', { name: 'Hide this checklist' }))
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
    expect(JSON.parse(localStorage.getItem(onboardingKey('u1')) ?? '{}').dismissed).toBe(true)
    expect(localStorage.getItem(onboardingKey('u2'))).toBeNull()
  })

  it('stays hidden on the next load for the same user but not for another', async () => {
    localStorage.setItem(onboardingKey('u1'), JSON.stringify({ dismissed: true }))
    dashboardGet.mockResolvedValue(dashboard())
    const first = renderChecklist()
    await waitFor(() => expect(dashboardGet).toHaveBeenCalled())
    await new Promise((r) => setTimeout(r, 20))
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
    first.unmount()
    renderChecklist({ user: { id: 'u2', ai_consent_required: false } as AuthUser })
    expect(await screen.findByRole('list')).toBeInTheDocument()
  })

  it('still works for the session when localStorage throws', async () => {
    dashboardGet.mockResolvedValue(dashboard())
    const get = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('denied')
    })
    const set = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('quota')
    })
    try {
      renderChecklist()
      await userEvent.click(await screen.findByRole('button', { name: 'Hide this checklist' }))
      expect(screen.queryByRole('list')).not.toBeInTheDocument()
    } finally {
      get.mockRestore()
      set.mockRestore()
    }
  })

  it('a stored value that is not JSON is ignored', async () => {
    localStorage.setItem(onboardingKey('u1'), '{nope')
    dashboardGet.mockResolvedValue(dashboard())
    renderChecklist()
    expect(await screen.findByRole('list')).toBeInTheDocument()
  })

  it('shows a finished checklist again when re-opened from settings', async () => {
    localStorage.setItem(onboardingKey('u1'), JSON.stringify({ reopened: true }))
    dashboardGet.mockResolvedValue(dashboard({ courses: [COURSE] }))
    courseDetail.mockResolvedValue(detailWithSummary('s1'))
    spotsList.mockResolvedValue(spots(3))
    renderChecklist()
    const items = await screen.findAllByRole('listitem')
    expect(items.every((li) => li.getAttribute('data-status') === 'done')).toBe(true)
  })
})

describe('AI consent', () => {
  const NEEDS = { id: 'u1', ai_consent_required: true } as AuthUser

  it('explains consent and opens the existing dialog before upload, then continues', async () => {
    dashboardGet.mockResolvedValue(dashboard())
    requestConsent.mockResolvedValue(true)
    renderChecklist({ user: NEEDS })
    expect(await screen.findByText(/your lecture text is sent to it/i)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Upload a lecture' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Review and agree' }))
    expect(requestConsent).toHaveBeenCalledTimes(1)
    expect((JSON.parse((await screen.findByTestId('loc')).textContent ?? '{}')).path).toBe('/upload')
  })

  it('stays on the dashboard when consent is declined', async () => {
    dashboardGet.mockResolvedValue(dashboard())
    requestConsent.mockResolvedValue(false)
    renderChecklist({ user: NEEDS })
    await userEvent.click(await screen.findByRole('button', { name: 'Review and agree' }))
    await waitFor(() => expect(requestConsent).toHaveBeenCalled())
    expect(screen.queryByTestId('loc')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Review and agree' })).toBeInTheDocument()
  })
})
