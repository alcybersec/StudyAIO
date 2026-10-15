import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { TonightCard } from './TonightCard'
import { weakSpotsApi } from '../../api/weakSpots'
import { recordUsageEvent } from '../../api/usage'
import type { TonightPlan } from '../../types'

vi.mock('../../api/weakSpots', () => ({
  weakSpotsApi: { tonight: vi.fn(), refreshTonight: vi.fn() },
}))
vi.mock('../../api/usage', () => ({ recordUsageEvent: vi.fn() }))

const tonight = vi.mocked(weakSpotsApi.tonight)
const refreshTonight = vi.mocked(weakSpotsApi.refreshTonight)

const PLAN: TonightPlan = {
  plan_date: '2026-10-15',
  minutes: 25,
  version: 1,
  algorithm_version: 1,
  built_at: '2026-10-15T18:00:00Z',
  total_minutes: 8,
  done_count: 1,
  items: [
    { item_type: 'card', item_id: 'card-1', course_id: 'c1', course_code: 'CSIT302', week: 3, reason: 'review', minutes: 2, done: true },
    { item_type: 'card', item_id: 'card-2', course_id: 'c1', course_code: 'CSIT302', week: 3, reason: 'review', minutes: 2, done: false },
    { item_type: 'quiz', item_id: 'quiz-1', course_id: 'c1', course_code: 'CSIT302', week: 3, reason: 'targeted', minutes: 3, done: false },
  ],
  focus: [{ course_id: 'c1', course_code: 'CSIT302', week: 3, status: 'weak', weakness: 0.7, priority: 1.2, days_to_exam: 4 }],
  diagnostic: null,
}

function LocationProbe() {
  const loc = useLocation()
  return <pre data-testid="loc">{JSON.stringify({ path: loc.pathname + loc.search, state: loc.state })}</pre>
}

function renderCard() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/" element={<TonightCard />} />
          <Route path="/study" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('TonightCard', () => {
  it('shows a busy skeleton while loading', () => {
    tonight.mockReturnValue(new Promise(() => {}))
    renderCard()
    expect(screen.getByText('Study tonight')).toBeInTheDocument()
    expect(document.querySelector('[aria-busy="true"]')).not.toBeNull()
  })

  it('shows an error with retry, and retry refetches', async () => {
    tonight.mockRejectedValueOnce(new Error('boom'))
    renderCard()
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    tonight.mockResolvedValueOnce(PLAN)
    await userEvent.click(screen.getByRole('button', { name: /retry/i }))
    expect(await screen.findByText(/3 items/)).toBeInTheDocument()
  })

  it('shows an empty state with a way forward when nothing is planned', async () => {
    tonight.mockResolvedValue({ ...PLAN, items: [], focus: [], done_count: 0, total_minutes: 0 })
    renderCard()
    expect(await screen.findByText('Nothing to practise tonight')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'See your mastery map' })).toHaveAttribute('href', '/study?tab=mastery')
  })

  it('shows items, minutes, done count, focus weeks with their why, and a practice badge', async () => {
    tonight.mockResolvedValue(PLAN)
    renderCard()
    expect(await screen.findByText(/3 items · about 8 min · 1 done/)).toBeInTheDocument()
    expect(screen.getByText(/Weak · exam in 4d/)).toBeInTheDocument()
    expect(screen.getByText('Practice')).toBeInTheDocument()
  })

  it('records study_plan_viewed once the plan is shown', async () => {
    tonight.mockResolvedValue(PLAN)
    renderCard()
    await screen.findByText(/3 items/)
    expect(recordUsageEvent).toHaveBeenCalledWith('study_plan_viewed')
    expect(recordUsageEvent).toHaveBeenCalledTimes(1)
  })

  it('starts the study runner with the ids of the items that are not done', async () => {
    tonight.mockResolvedValue(PLAN)
    renderCard()
    await userEvent.click(await screen.findByRole('button', { name: 'Start' }))
    const probe = JSON.parse((await screen.findByTestId('loc')).textContent ?? '{}')
    expect(probe.path).toBe('/study?tab=timed')
    expect(probe.state.planRun).toMatchObject({
      cardIds: ['card-2'],
      quizIds: ['quiz-1'],
      minutes: 5,
      courseCodes: ['CSIT302'],
    })
  })

  it('refreshes the plan on request and shows the rebuilt one', async () => {
    tonight.mockResolvedValue(PLAN)
    refreshTonight.mockResolvedValue({ ...PLAN, version: 2, items: PLAN.items.slice(0, 2), done_count: 1 })
    renderCard()
    await userEvent.click(await screen.findByRole('button', { name: /refresh plan/i }))
    expect(refreshTonight).toHaveBeenCalledTimes(1)
    expect(await screen.findByText(/2 items/)).toBeInTheDocument()
  })

  it('keeps the plan on screen and says so when a refresh fails', async () => {
    tonight.mockResolvedValue(PLAN)
    refreshTonight.mockRejectedValue(new Error('boom'))
    renderCard()
    await userEvent.click(await screen.findByRole('button', { name: /refresh plan/i }))
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect(screen.getByText(/3 items/)).toBeInTheDocument()
  })
})
