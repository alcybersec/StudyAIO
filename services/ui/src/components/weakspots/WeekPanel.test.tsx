import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '../../i18n'
import { WeekPanel } from './WeekPanel'
import { weakSpotsApi } from '../../api/weakSpots'
import { masteryLabel } from '../../lib/weakSpots'
import type { WeakSpotCourse, WeakSpotWeek } from '../../types'

vi.mock('../../api/weakSpots', () => ({
  weakSpotsApi: { diagnostic: vi.fn(), requestTargeted: vi.fn(), targeted: vi.fn(), refreshTonight: vi.fn() },
}))
const diagnostic = vi.mocked(weakSpotsApi.diagnostic)

const week = (status: WeakSpotWeek['status']): WeakSpotWeek => ({
  week: 4,
  status,
  weakness: status === 'unknown' ? null : 0.6,
  confidence: 0.4,
  urgency: 0,
  priority: 0,
  evidence: { quiz_attempts: 1, quiz_accuracy: null, cards_reviewed: 0, avg_ease: null, lapsed_cards: 0, overdue_cards: 0 },
  next_exam: null,
})
const course: WeakSpotCourse = { course_id: 'c1', course_code: 'CSIT302', weeks: [] }

function Probe() {
  const loc = useLocation()
  return <pre data-testid="loc">{JSON.stringify({ path: loc.pathname + loc.search, state: loc.state })}</pre>
}

function renderPanel(status: WeakSpotWeek['status']) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/" element={<WeekPanel course={course} week={week(status)} />} />
          <Route path="/study" element={<Probe />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => vi.clearAllMocks())

describe('WeekPanel', () => {
  it('offers the diagnostic only on unknown weeks', () => {
    renderPanel('weak')
    expect(screen.queryByRole('button', { name: /short check-in/i })).toBeNull()
    expect(screen.getByRole('button', { name: /practise this week: questions/i })).toBeInTheDocument()
  })

  it('starts the diagnostic set from the API in the study runner', async () => {
    diagnostic.mockResolvedValue({ course_id: 'c1', week: 4, question_ids: ['q1', 'q2', 'q3'], needs_generation: false })
    renderPanel('unknown')
    await userEvent.click(screen.getByRole('button', { name: /short check-in/i }))
    expect(diagnostic).toHaveBeenCalledWith('c1', 4)
    const probe = JSON.parse((await screen.findByTestId('loc')).textContent ?? '{}')
    expect(probe.state.planRun).toMatchObject({ quizIds: ['q1', 'q2', 'q3'], cardIds: [], courseCodes: ['CSIT302'] })
  })

  it('points to generation when the week has no questions', async () => {
    diagnostic.mockResolvedValue({ course_id: 'c1', week: 4, question_ids: [], needs_generation: true })
    renderPanel('unknown')
    await userEvent.click(screen.getByRole('button', { name: /short check-in/i }))
    expect(await screen.findByText(/no questions yet/i)).toBeInTheDocument()
    expect(screen.queryByTestId('loc')).toBeNull()
  })

  it('shows an error when the check-in cannot load', async () => {
    diagnostic.mockRejectedValue(new Error('boom'))
    renderPanel('unknown')
    await userEvent.click(screen.getByRole('button', { name: /short check-in/i }))
    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })
})

describe('Russian', () => {
  it('translates the state labels', async () => {
    await i18n.changeLanguage('ru')
    try {
      expect(masteryLabel('unknown')).toBe('Мало данных')
      expect(masteryLabel('weak')).toBe('Слабо')
      expect(masteryLabel('ok')).toBe('Нормально')
      expect(masteryLabel('solid')).toBe('Уверенно')
    } finally {
      await i18n.changeLanguage('en')
    }
  })
})
