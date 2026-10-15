import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { QuizTab } from './QuizTab'
import { assetsApi } from '../../api/endpoints'
import type { QuizQuestion } from '../../types'

vi.mock('../../api/endpoints', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/endpoints')>()
  return {
    ...actual,
    assetsApi: { quiz: vi.fn(), createQuiz: vi.fn(), updateQuiz: vi.fn(), deleteQuiz: vi.fn() },
    studyApi: {
      ...actual.studyApi,
      stats: vi.fn().mockResolvedValue(null),
      quizAttempt: vi.fn().mockResolvedValue({}),
    },
  }
})

const mcq = (over: Partial<QuizQuestion>): QuizQuestion => ({
  id: 'q1',
  course_id: 'c1',
  week: 1,
  question_type: 'multiple_choice',
  question: 'First?',
  options_json: ['A. a', 'B. b'],
  correct_answer: 'A',
  explanation: 'because',
  source_artifact_id: 'a1',
  source_page_ref: 1,
  generation_version: 1,
  origin: 'pipeline',
  created_at: '2026-01-01T00:00:00Z',
  ...over,
})

describe('quiz Next', () => {
  beforeEach(() => vi.clearAllMocks())

  it('clears the previous question options and result after Next', async () => {
    const user = userEvent.setup()
    vi.mocked(assetsApi.quiz).mockResolvedValue([
      mcq({}),
      mcq({ id: 'q2', question: 'Second?', options_json: ['A. x', 'B. y'], correct_answer: 'B' }),
    ])
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <QuizTab courseCode="CSIT302" week={1} />
        </MemoryRouter>
      </QueryClientProvider>,
    )
    await screen.findByText('First?')
    await user.click(screen.getAllByRole('radio')[0])
    await user.click(screen.getByRole('button', { name: 'Submit' }))
    expect(screen.getByTestId('quiz-result')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByText('Second?')).toBeInTheDocument()
    expect(screen.queryByText('First?')).not.toBeInTheDocument()
    expect(screen.getAllByRole('radio')).toHaveLength(2)
    expect(screen.queryByTestId('quiz-result')).not.toBeInTheDocument()
  })
})
