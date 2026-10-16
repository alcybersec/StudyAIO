import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { FirstRunChecklist } from './FirstRunChecklist'
import { AuthContext, type AuthContextValue } from '../../contexts/AuthContext'
import { ConsentContext } from '../../contexts/consentContext'
import { PipelineEventsContext, type PipelineEventsValue } from '../../contexts/pipelineProgress'
import { legacyOnboardingKey } from '../../hooks/useOnboarding'
import { onboardingApi } from '../../api/onboarding'
import { weakSpotsApi } from '../../api/weakSpots'
import { AppApiError } from '../../api/errors'
import type { AuthUser, OnboardingStatus } from '../../types'

vi.mock('../../api/onboarding', () => ({
  onboardingApi: { get: vi.fn(), setChecklist: vi.fn() },
}))
vi.mock('../../api/weakSpots', () => ({
  weakSpotsApi: { diagnostic: vi.fn() },
}))

const onboardingGet = vi.mocked(onboardingApi.get)
const setChecklist = vi.mocked(onboardingApi.setChecklist)
const diagnostic = vi.mocked(weakSpotsApi.diagnostic)

const USER = { id: 'u1', ai_consent_required: false } as AuthUser

const status = (over: Partial<OnboardingStatus> = {}): OnboardingStatus => ({
  phase: 'new',
  steps: { upload: 'active', summary: 'locked', check_in: 'locked' },
  summary_target: null,
  checklist: 'auto',
  visible: true,
  ...over,
})

const WITH_SUMMARY = status({
  phase: 'has_summary',
  steps: { upload: 'done', summary: 'active', check_in: 'active' },
  summary_target: { course_id: 'c1', course_code: 'CSIT302', week: 2 },
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
  onboardingGet.mockResolvedValue(status())
})

describe('steps come from the server', () => {
  it('new user: upload is the active step, the rest are locked', async () => {
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
    expect(onboardingGet).toHaveBeenCalledTimes(1)
  })

  it('processing: upload is done, shows live pipeline progress, summary still locked', async () => {
    onboardingGet.mockResolvedValue(
      status({ phase: 'processing', steps: { upload: 'done', summary: 'locked', check_in: 'locked' } }),
    )
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

  it('has a summary: links to the server-provided target and enables the check-in', async () => {
    onboardingGet.mockResolvedValue(WITH_SUMMARY)
    renderChecklist()
    const link = await screen.findByRole('link', { name: 'Open summary' })
    expect(link).toHaveAttribute('href', '/courses/CSIT302/weeks/2')
    expect(screen.getByRole('button', { name: 'Start the check-in' })).toBeEnabled()
    expect(screen.getAllByRole('listitem')[0]).toHaveAttribute('data-status', 'done')
  })

  it('renders nothing when the server says it is not visible', async () => {
    onboardingGet.mockResolvedValue(status({ phase: 'done', visible: false }))
    renderChecklist()
    await waitFor(() => expect(onboardingGet).toHaveBeenCalled())
    await new Promise((r) => setTimeout(r, 20))
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })

  it('renders a finished checklist when the server keeps it visible (pinned)', async () => {
    onboardingGet.mockResolvedValue(
      status({
        phase: 'done',
        checklist: 'pinned',
        steps: { upload: 'done', summary: 'done', check_in: 'done' },
        summary_target: { course_id: 'c1', course_code: 'CSIT302', week: 2 },
      }),
    )
    renderChecklist()
    const items = await screen.findAllByRole('listitem')
    expect(items.every((li) => li.getAttribute('data-status') === 'done')).toBe(true)
  })

  it('renders nothing while loading', () => {
    onboardingGet.mockReturnValue(new Promise(() => {}))
    renderChecklist()
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows an error with a retry when the status cannot be loaded', async () => {
    onboardingGet.mockRejectedValueOnce(new AppApiError('boom', 500))
    renderChecklist()
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    onboardingGet.mockResolvedValue(status())
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByRole('list')).toBeInTheDocument()
  })
})

describe('check-in step', () => {
  it('starts the diagnostic for the summarised week and hands it to the study runner', async () => {
    onboardingGet.mockResolvedValue(WITH_SUMMARY)
    diagnostic.mockResolvedValue({ course_id: 'c1', week: 2, question_ids: ['q1', 'q2'], needs_generation: false })
    renderChecklist()
    await userEvent.click(await screen.findByRole('button', { name: 'Start the check-in' }))
    const probe = JSON.parse((await screen.findByTestId('loc')).textContent ?? '{}')
    expect(diagnostic).toHaveBeenCalledWith('c1', 2)
    expect(probe.path).toBe('/study?tab=timed')
    expect(probe.state.planRun).toMatchObject({ quizIds: ['q1', 'q2'], courseCodes: ['CSIT302'] })
  })

  it('says so when the week has no questions yet instead of navigating', async () => {
    onboardingGet.mockResolvedValue(WITH_SUMMARY)
    diagnostic.mockResolvedValue({ course_id: 'c1', week: 2, question_ids: [], needs_generation: true })
    renderChecklist()
    await userEvent.click(await screen.findByRole('button', { name: 'Start the check-in' }))
    expect(await screen.findByText(/no questions yet/i)).toBeInTheDocument()
    expect(screen.queryByTestId('loc')).not.toBeInTheDocument()
  })
})

describe('dismissal', () => {
  it('PATCHes dismissed and hides the checklist from the response', async () => {
    setChecklist.mockResolvedValue(status({ checklist: 'dismissed', visible: false }))
    renderChecklist()
    await userEvent.click(await screen.findByRole('button', { name: 'Hide this checklist' }))
    expect(setChecklist).toHaveBeenCalledWith('dismissed')
    await waitFor(() => expect(screen.queryByRole('list')).not.toBeInTheDocument())
  })

  it('keeps the checklist and says so when the PATCH fails', async () => {
    setChecklist.mockRejectedValue(new AppApiError('boom', 500))
    renderChecklist()
    await userEvent.click(await screen.findByRole('button', { name: 'Hide this checklist' }))
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.getByRole('list')).toBeInTheDocument()
  })

  it('is reachable by keyboard', async () => {
    setChecklist.mockResolvedValue(status({ checklist: 'dismissed', visible: false }))
    renderChecklist()
    const hide = await screen.findByRole('button', { name: 'Hide this checklist' })
    hide.focus()
    await userEvent.keyboard('{Enter}')
    expect(setChecklist).toHaveBeenCalledWith('dismissed')
  })
})

describe('legacy localStorage migration', () => {
  it('sends one dismissed PATCH, clears the key and does not show the checklist', async () => {
    localStorage.setItem(legacyOnboardingKey('u1'), JSON.stringify({ dismissed: true, summaryRead: true }))
    setChecklist.mockResolvedValue(status({ checklist: 'dismissed', visible: false }))
    renderChecklist()
    await waitFor(() => expect(localStorage.getItem(legacyOnboardingKey('u1'))).toBeNull())
    expect(setChecklist).toHaveBeenCalledTimes(1)
    expect(setChecklist).toHaveBeenCalledWith('dismissed')
    expect(onboardingGet).not.toHaveBeenCalled()
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })

  it('keeps the key when the PATCH fails, so it is retried', async () => {
    localStorage.setItem(legacyOnboardingKey('u1'), JSON.stringify({ dismissed: true }))
    setChecklist.mockRejectedValue(new AppApiError('boom', 500))
    renderChecklist()
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(localStorage.getItem(legacyOnboardingKey('u1'))).not.toBeNull()
  })

  it('a legacy entry without a dismissal is cleared without a PATCH', async () => {
    localStorage.setItem(legacyOnboardingKey('u1'), JSON.stringify({ reopened: true }))
    renderChecklist()
    expect(await screen.findByRole('list')).toBeInTheDocument()
    expect(setChecklist).not.toHaveBeenCalled()
    expect(localStorage.getItem(legacyOnboardingKey('u1'))).toBeNull()
  })

  it('another user’s legacy dismissal is left alone', async () => {
    localStorage.setItem(legacyOnboardingKey('u2'), JSON.stringify({ dismissed: true }))
    renderChecklist()
    expect(await screen.findByRole('list')).toBeInTheDocument()
    expect(setChecklist).not.toHaveBeenCalled()
    expect(localStorage.getItem(legacyOnboardingKey('u2'))).not.toBeNull()
  })

  it('a corrupt legacy value is ignored and cleared', async () => {
    localStorage.setItem(legacyOnboardingKey('u1'), '{nope')
    renderChecklist()
    expect(await screen.findByRole('list')).toBeInTheDocument()
    expect(setChecklist).not.toHaveBeenCalled()
  })
})

describe('AI consent', () => {
  const NEEDS = { id: 'u1', ai_consent_required: true } as AuthUser

  it('explains consent and opens the existing dialog before upload, then continues', async () => {
    requestConsent.mockResolvedValue(true)
    renderChecklist({ user: NEEDS })
    expect(await screen.findByText(/your lecture text is sent to it/i)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Upload a lecture' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Review and agree' }))
    expect(requestConsent).toHaveBeenCalledTimes(1)
    expect(JSON.parse((await screen.findByTestId('loc')).textContent ?? '{}').path).toBe('/upload')
  })

  it('stays on the dashboard when consent is declined', async () => {
    requestConsent.mockResolvedValue(false)
    renderChecklist({ user: NEEDS })
    await userEvent.click(await screen.findByRole('button', { name: 'Review and agree' }))
    await waitFor(() => expect(requestConsent).toHaveBeenCalled())
    expect(screen.queryByTestId('loc')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Review and agree' })).toBeInTheDocument()
  })
})
