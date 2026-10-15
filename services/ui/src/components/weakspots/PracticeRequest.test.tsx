import { MemoryRouter } from 'react-router-dom'
import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { PracticeRequest } from './PracticeRequest'
import { weakSpotsApi } from '../../api/weakSpots'
import { AppApiError, classifyResponse } from '../../api/errors'
import { GENERATION_POLL_MS } from '../../hooks/useWeakSpots'
import type { TargetedGeneration, TonightPlan } from '../../types'

vi.mock('../../api/weakSpots', () => ({
  weakSpotsApi: { requestTargeted: vi.fn(), targeted: vi.fn(), refreshTonight: vi.fn() },
}))

const request = vi.mocked(weakSpotsApi.requestTargeted)
const poll = vi.mocked(weakSpotsApi.targeted)
const refreshTonight = vi.mocked(weakSpotsApi.refreshTonight)

const gen = (over: Partial<TargetedGeneration> = {}): TargetedGeneration => ({
  id: 'gen-1',
  course_id: 'c1',
  week: 3,
  kind: 'quiz',
  status: 'queued',
  requested_count: 5,
  created_count: 0,
  dropped_duplicate_count: 0,
  dropped_uncited_count: 0,
  item_ids: [],
  created_at: '2026-10-15T18:00:00Z',
  completed_at: null,
  ...over,
})

function renderRequest() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <PracticeRequest courseId="c1" week={3} kind="quiz" label="Practise" />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

const tick = (ms = GENERATION_POLL_MS) => act(() => vi.advanceTimersByTimeAsync(ms))

beforeEach(() => {
  vi.clearAllMocks()
  vi.useFakeTimers({ shouldAdvanceTime: true })
})
afterEach(() => {
  vi.useRealTimers()
})

describe('PracticeRequest', () => {
  it('posts the request, polls until completed, then offers to refresh the plan', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    request.mockResolvedValue(gen())
    poll
      .mockResolvedValueOnce(gen({ status: 'queued' }))
      .mockResolvedValueOnce(gen({ status: 'running' }))
      .mockResolvedValue(gen({ status: 'completed', created_count: 4, item_ids: ['a', 'b', 'c', 'd'] }))
    refreshTonight.mockResolvedValue({ items: [], focus: [] } as unknown as TonightPlan)

    renderRequest()
    await user.click(screen.getByRole('button', { name: 'Practise' }))
    expect(request).toHaveBeenCalledWith({ course_id: 'c1', week: 3, kind: 'quiz' })

    expect(await screen.findByText(/Generating practice/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Practise' })).toBeDisabled()

    await tick()
    await tick()
    await tick()
    expect(await screen.findByText(/4 new practice items are ready/)).toBeInTheDocument()
    expect(poll).toHaveBeenCalledWith('gen-1')

    await user.click(screen.getByRole('button', { name: /refresh tonight's plan/i }))
    expect(refreshTonight).toHaveBeenCalledTimes(1)
    expect(await screen.findByText(/plan is updated/i)).toBeInTheDocument()
  })

  it('treats the in-flight 200 like a new 202: it polls the returned id', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    request.mockResolvedValue(gen({ id: 'already-running', status: 'running' }))
    poll.mockResolvedValue(gen({ id: 'already-running', status: 'running' }))

    renderRequest()
    await user.click(screen.getByRole('button', { name: 'Practise' }))
    await tick()
    expect(poll).toHaveBeenCalledWith('already-running')
    expect(screen.getByText(/Generating practice/)).toBeInTheDocument()
  })

  it('stops polling once the generation is completed', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    request.mockResolvedValue(gen())
    poll.mockResolvedValue(gen({ status: 'completed', created_count: 1 }))

    renderRequest()
    await user.click(screen.getByRole('button', { name: 'Practise' }))
    await screen.findByText(/1 new practice item is ready/)
    const calls = poll.mock.calls.length
    await tick(GENERATION_POLL_MS * 3)
    expect(poll.mock.calls.length).toBe(calls)
  })

  it('says so when a completed generation added nothing', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    request.mockResolvedValue(gen())
    poll.mockResolvedValue(gen({ status: 'completed', created_count: 0, dropped_duplicate_count: 5 }))

    renderRequest()
    await user.click(screen.getByRole('button', { name: 'Practise' }))
    expect(await screen.findByText(/Nothing new to add/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /refresh tonight's plan/i })).toBeNull()
  })

  it('shows a clear message with the reset time on 429 targeted_daily_cap', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    request.mockRejectedValue(classifyResponse(429, { code: 'targeted_daily_cap', detail: 'Daily limit reached' }))

    renderRequest()
    await user.click(screen.getByRole('button', { name: 'Practise' }))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/used today's practice generations/)
    expect(alert).toHaveTextContent(/00:00 UTC/)
    expect(alert).not.toHaveTextContent(/Rate limited/)
    expect(poll).not.toHaveBeenCalled()
  })

  it('explains a declined AI consent (403 ai_consent_required) and lets the user retry', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    request.mockRejectedValue(classifyResponse(403, { code: 'ai_consent_required', consent_version: 2 }))

    renderRequest()
    await user.click(screen.getByRole('button', { name: 'Practise' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/needs your OK to use AI/)
    expect(screen.getByRole('button', { name: 'Practise' })).toBeEnabled()
  })

  it('maps a quota error (402) through the shared error mapper', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    request.mockRejectedValue(new AppApiError('quota', 402, { resource: 'ai_calls' }))

    renderRequest()
    await user.click(screen.getByRole('button', { name: 'Practise' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('This is over your plan limit.')
  })

  it('reports a failed generation without leaking provider text', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    request.mockResolvedValue(gen())
    poll.mockResolvedValue(gen({ status: 'failed', error_code: 'agent_error' }))

    renderRequest()
    await user.click(screen.getByRole('button', { name: 'Practise' }))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/didn't finish/)
    expect(alert).not.toHaveTextContent('agent_error')
  })
})
