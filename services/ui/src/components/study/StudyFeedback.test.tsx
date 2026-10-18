import { MemoryRouter } from 'react-router-dom'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { toast } from 'sonner'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { FlashcardsStudyTab } from './FlashcardsStudyTab'
import { TimedStudyTab } from './TimedStudyTab'
import { studyApi, assetsApi } from '../../api/endpoints'
import { aiFeedbackApi } from '../../api/aiFeedback'
import { NotFoundError } from '../../api/errors'
import type { Flashcard, QuizQuestion } from '../../types'

vi.mock('../../api/endpoints', () => ({
  studyApi: { due: vi.fn(), quizAttempt: vi.fn() },
  assetsApi: { quiz: vi.fn() },
  examsApi: { recordSession: vi.fn() },
}))
vi.mock('../../api/aiFeedback', () => ({
  aiFeedbackApi: { mine: vi.fn(), put: vi.fn(), clear: vi.fn() },
}))
vi.mock('sonner', () => ({ toast: { error: vi.fn(), info: vi.fn() } }))

const dueCards: Flashcard[] = []
vi.mock('../../hooks/useApi', () => ({
  useTimedPlan: () => ({ mutateAsync: vi.fn(), isPending: false, isError: false }),
  useRecordReview: () => ({ mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false }),
  useStudyDue: () => ({ data: dueCards, isLoading: false, refetch: vi.fn() }),
  useExamDetail: () => ({ data: undefined }),
}))

const feedback = vi.mocked(aiFeedbackApi)

const card = (over: Partial<Flashcard> = {}): Flashcard => ({
  id: 'card-1',
  course_id: 'c1',
  week: 3,
  front: 'What is a mutex?',
  back: 'A lock',
  tags: [],
  source_artifact_id: 'a1',
  source_page_ref: 0,
  generation_version: 1,
  created_at: '2026-10-15T00:00:00Z',
  ...over,
})

const quiz = {
  id: 'quiz-1',
  course_id: 'c1',
  week: 3,
  question_type: 'short_answer',
  question: 'Name the lock primitive',
  options_json: null,
  correct_answer: 'mutex',
  explanation: null,
  source_page_ref: 0,
  origin: 'generated',
} as unknown as QuizQuestion

const thumbUp = () => screen.getByRole('button', { name: 'Helpful' })
const thumbDown = () => screen.getByRole('button', { name: 'Not helpful' })

function renderWith(ui: React.ReactElement, entry: string | object = '/study') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[entry as string]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  dueCards.length = 0
  feedback.mine.mockResolvedValue([])
  feedback.put.mockResolvedValue({
    target_type: 'flashcard',
    target_id: 'card-1',
    rating: 1,
    reason: null,
    comment: null,
  })
})

describe('flashcard study runner feedback', () => {
  beforeEach(() => {
    dueCards.push(card(), card({ id: 'card-2' }))
  })

  it('rates the current card as a flashcard, loading votes for the whole deck in one request', async () => {
    renderWith(<FlashcardsStudyTab />, '/study?exam=e1&course=CSIT302')
    await userEvent.click(thumbUp())
    expect(feedback.put).toHaveBeenCalledWith({ target_type: 'flashcard', target_id: 'card-1', rating: 1 })
    expect(feedback.mine).toHaveBeenCalledWith('flashcard', ['card-1', 'card-2'])
    expect(thumbUp()).toHaveAttribute('aria-pressed', 'true')
  })

  it('sends a thumbs-down with its reason', async () => {
    renderWith(<FlashcardsStudyTab />, '/study?exam=e1&course=CSIT302')
    await userEvent.click(thumbDown())
    await userEvent.click(screen.getByLabelText('Unclear'))
    await userEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    expect(feedback.put).toHaveBeenCalledWith({
      target_type: 'flashcard',
      target_id: 'card-1',
      rating: -1,
      reason: 'unclear',
    })
  })

  it('says the card was archived on a 404 and leaves the thumb unpressed', async () => {
    feedback.put.mockRejectedValue(new NotFoundError('gone', 404))
    renderWith(<FlashcardsStudyTab />, '/study?exam=e1&course=CSIT302')
    await userEvent.click(thumbUp())
    await waitFor(() => expect(toast.info).toHaveBeenCalledWith('This item was archived, so it can no longer be rated.'))
    expect(toast.error).not.toHaveBeenCalled()
    expect(thumbUp()).toHaveAttribute('aria-pressed', 'false')
  })

  it('keeps Enter on a thumb from flipping the card', async () => {
    renderWith(<FlashcardsStudyTab />, '/study?exam=e1&course=CSIT302')
    thumbUp().focus()
    await userEvent.keyboard('{Enter}')
    expect(feedback.put).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('button', { name: /Showing question/ })).toBeInTheDocument()
  })

  it('typing a reason does not rate the card', async () => {
    renderWith(<FlashcardsStudyTab />, '/study?exam=e1&course=CSIT302')
    await userEvent.click(thumbDown())
    await userEvent.click(screen.getByRole('button', { name: /Showing question/ }))
    await userEvent.type(screen.getByLabelText('Comment (optional)'), '1 2 3')
    expect(screen.getByLabelText('Comment (optional)')).toHaveValue('1 2 3')
    expect(screen.getByText(/Card 1 of 2/)).toBeInTheDocument()
  })
})

describe('timed study runner feedback', () => {
  const run = (over: object) => ({
    pathname: '/study',
    search: '?tab=timed',
    state: { planRun: { cardIds: [], quizIds: [], minutes: 2, courseCodes: ['CSIT302'], ...over } },
  })

  it('rates a card as a flashcard', async () => {
    vi.mocked(studyApi.due).mockResolvedValue([card()])
    vi.mocked(assetsApi.quiz).mockResolvedValue([])
    renderWith(<TimedStudyTab />, run({ cardIds: ['card-1'] }) as never)
    await screen.findByText('What is a mutex?')
    await userEvent.click(thumbDown())
    await userEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    expect(feedback.put).toHaveBeenCalledWith({ target_type: 'flashcard', target_id: 'card-1', rating: -1 })
  })

  it('rates a quiz item as a quiz_question and survives an archived 404', async () => {
    vi.mocked(studyApi.due).mockResolvedValue([])
    vi.mocked(assetsApi.quiz).mockResolvedValue([quiz])
    feedback.put.mockRejectedValue(new NotFoundError('gone', 404))
    renderWith(<TimedStudyTab />, run({ quizIds: ['quiz-1'] }) as never)
    await screen.findByText('Name the lock primitive')
    await userEvent.click(thumbUp())
    expect(feedback.put).toHaveBeenCalledWith({ target_type: 'quiz_question', target_id: 'quiz-1', rating: 1 })
    expect(feedback.mine).toHaveBeenCalledWith('quiz_question', ['quiz-1'])
    await waitFor(() => expect(toast.info).toHaveBeenCalled())
    expect(thumbUp()).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByText('Name the lock primitive')).toBeInTheDocument()
  })

  it('p typed in the reason box does not pause the session', async () => {
    vi.mocked(studyApi.due).mockResolvedValue([])
    vi.mocked(assetsApi.quiz).mockResolvedValue([quiz])
    renderWith(<TimedStudyTab />, run({ quizIds: ['quiz-1'] }) as never)
    await screen.findByText('Name the lock primitive')
    await userEvent.click(thumbDown())
    await userEvent.type(screen.getByLabelText('Comment (optional)'), 'p')
    expect(screen.getByRole('button', { name: 'Pause' })).toBeInTheDocument()
  })
})
