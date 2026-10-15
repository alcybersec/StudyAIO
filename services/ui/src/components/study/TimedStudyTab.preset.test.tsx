import { MemoryRouter } from 'react-router-dom'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { TimedStudyTab } from './TimedStudyTab'
import { studyApi, assetsApi } from '../../api/endpoints'
import type { Flashcard, QuizQuestion } from '../../types'

vi.mock('../../api/endpoints', () => ({
  studyApi: { due: vi.fn(), quizAttempt: vi.fn() },
  assetsApi: { quiz: vi.fn() },
  examsApi: { recordSession: vi.fn() },
}))
vi.mock('../../hooks/useApi', () => ({
  useTimedPlan: () => ({ mutateAsync: vi.fn(), isPending: false, isError: false }),
  useRecordReview: () => ({ mutateAsync: vi.fn() }),
}))

const card = (over: Partial<Flashcard>): Flashcard => ({
  id: 'card-1',
  course_id: 'c1',
  week: 3,
  front: 'What is a mutex?',
  back: 'A lock',
  tags: [],
  source_artifact_id: 'a1',
  source_page_ref: 7,
  generation_version: 1,
  created_at: '2026-10-15T00:00:00Z',
  ...over,
})

function renderRunner(planRun: object) {
  const client = new QueryClient()
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[{ pathname: '/study', search: '?tab=timed', state: { planRun } }]}>
        <TimedStudyTab />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => vi.clearAllMocks())

describe('TimedStudyTab started from tonight\'s plan', () => {
  it('runs exactly the given ids and shows the practice badge and citation chip', async () => {
    vi.mocked(studyApi.due).mockResolvedValue([card({ id: 'other' }), card({ id: 'card-1', origin: 'targeted' })])
    vi.mocked(assetsApi.quiz).mockResolvedValue([] as QuizQuestion[])

    renderRunner({ cardIds: ['card-1'], quizIds: [], minutes: 2, courseCodes: ['CSIT302'] })

    expect(await screen.findByText('What is a mutex?')).toBeInTheDocument()
    expect(studyApi.due).toHaveBeenCalledWith('CSIT302', undefined, 11)
    expect(screen.getByText('Practice')).toBeInTheDocument()
    expect(screen.getByLabelText('Page 7')).toBeInTheDocument()
    expect(screen.getByText('1 / 1')).toBeInTheDocument()
  })

  it('shows an error with retry when the items cannot be loaded', async () => {
    vi.mocked(studyApi.due).mockRejectedValue(new Error('boom'))
    renderRunner({ cardIds: ['card-1'], quizIds: [], minutes: 2, courseCodes: ['CSIT302'] })
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })
})
