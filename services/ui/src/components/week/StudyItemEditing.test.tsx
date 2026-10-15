import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { FlashcardsTab } from './FlashcardsTab'
import { QuizTab } from './QuizTab'
import { assetsApi } from '../../api/endpoints'
import { AppApiError, ValidationError } from '../../api/errors'
import type { Flashcard, QuizQuestion } from '../../types'

vi.mock('../../api/endpoints', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/endpoints')>()
  return {
    ...actual,
    assetsApi: {
      flashcards: vi.fn(),
      quiz: vi.fn(),
      createFlashcard: vi.fn(),
      updateFlashcard: vi.fn(),
      deleteFlashcard: vi.fn(),
      createQuiz: vi.fn(),
      updateQuiz: vi.fn(),
      deleteQuiz: vi.fn(),
    },
    studyApi: { ...actual.studyApi, stats: vi.fn().mockResolvedValue(null) },
  }
})

const card = (over: Partial<Flashcard> = {}): Flashcard => ({
  id: 'f1',
  course_id: 'c1',
  week: 3,
  front: 'What is a stack?',
  back: 'LIFO structure',
  tags: [],
  source_artifact_id: 'a1',
  source_page_ref: 2,
  generation_version: 1,
  origin: 'pipeline',
  created_at: '2026-01-01T00:00:00Z',
  ...over,
})

const mcq = (over: Partial<QuizQuestion> = {}): QuizQuestion => ({
  id: 'q1',
  course_id: 'c1',
  week: 3,
  question_type: 'multiple_choice',
  question: 'Which is LIFO?',
  options_json: ['A. Queue', 'B. Stack'],
  correct_answer: 'B',
  explanation: 'Stack pops the newest.',
  source_artifact_id: 'a1',
  source_page_ref: 1,
  generation_version: 1,
  origin: 'pipeline',
  created_at: '2026-01-01T00:00:00Z',
  ...over,
})

function renderUi(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('flashcard editing', () => {
  beforeEach(() => vi.clearAllMocks())

  it('edit saves the changes and shows the card under its NEW id with a Yours badge', async () => {
    const user = userEvent.setup()
    // First load returns the original; after the edit the server lists the new copy only.
    vi.mocked(assetsApi.flashcards).mockResolvedValueOnce([card()]).mockResolvedValue([
      card({ id: 'f2', front: 'What is a stack, exactly?', origin: 'user' }),
    ])
    vi.mocked(assetsApi.updateFlashcard).mockResolvedValue(
      card({ id: 'f2', front: 'What is a stack, exactly?', origin: 'user' }),
    )
    renderUi(<FlashcardsTab courseCode="CSIT302" week={3} />)

    await screen.findByText('What is a stack?')
    expect(screen.queryByText('Yours')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /^Edit$/ }))
    const dialog = await screen.findByRole('dialog')
    const front = within(dialog).getByLabelText('Front')
    await user.clear(front)
    await user.type(front, 'What is a stack, exactly?')
    await user.click(within(dialog).getByRole('button', { name: 'Save changes' }))

    await waitFor(() =>
      expect(assetsApi.updateFlashcard).toHaveBeenCalledWith('f1', {
        front: 'What is a stack, exactly?',
        back: 'LIFO structure',
      }),
    )
    expect(await screen.findByText('What is a stack, exactly?')).toBeInTheDocument()
    expect(screen.getByText('Yours')).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('blocks an empty front client-side and never calls the API', async () => {
    const user = userEvent.setup()
    vi.mocked(assetsApi.flashcards).mockResolvedValue([card()])
    renderUi(<FlashcardsTab courseCode="CSIT302" week={3} />)
    await screen.findByText('What is a stack?')
    await user.click(screen.getByRole('button', { name: /^Edit$/ }))
    const dialog = await screen.findByRole('dialog')
    await user.clear(within(dialog).getByLabelText('Front'))
    await user.click(within(dialog).getByRole('button', { name: 'Save changes' }))
    expect(await within(dialog).findByText('This field is required')).toBeInTheDocument()
    expect(assetsApi.updateFlashcard).not.toHaveBeenCalled()
  })

  it('delete asks for confirmation with Cancel focused, and only then calls the API', async () => {
    const user = userEvent.setup()
    vi.mocked(assetsApi.flashcards).mockResolvedValueOnce([card(), card({ id: 'f9', front: 'Second' })]).mockResolvedValue([
      card({ id: 'f9', front: 'Second' }),
    ])
    vi.mocked(assetsApi.deleteFlashcard).mockResolvedValue(undefined)
    renderUi(<FlashcardsTab courseCode="CSIT302" week={3} />)
    await screen.findByText('What is a stack?')

    await user.click(screen.getByRole('button', { name: /^Delete$/ }))
    const dialog = await screen.findByRole('dialog')
    expect(dialog).toHaveTextContent('What is a stack?')
    expect(within(dialog).getByRole('button', { name: 'Cancel' })).toHaveFocus()
    expect(assetsApi.deleteFlashcard).not.toHaveBeenCalled()

    await user.click(within(dialog).getByRole('button', { name: 'Delete' }))
    await waitFor(() => expect(assetsApi.deleteFlashcard).toHaveBeenCalledWith('f1'))
    expect(await screen.findByText('Second')).toBeInTheDocument()
    expect(screen.queryByText('What is a stack?')).not.toBeInTheDocument()
  })

  it('cancelling the delete dialog deletes nothing', async () => {
    const user = userEvent.setup()
    vi.mocked(assetsApi.flashcards).mockResolvedValue([card()])
    renderUi(<FlashcardsTab courseCode="CSIT302" week={3} />)
    await screen.findByText('What is a stack?')
    await user.click(screen.getByRole('button', { name: /^Delete$/ }))
    await user.click(await screen.findByRole('button', { name: 'Cancel' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(assetsApi.deleteFlashcard).not.toHaveBeenCalled()
  })

  it('typing a space in the editor does not flip the card behind it', async () => {
    const user = userEvent.setup()
    vi.mocked(assetsApi.flashcards).mockResolvedValue([card()])
    renderUi(<FlashcardsTab courseCode="CSIT302" week={3} />)
    await screen.findByText('What is a stack?')
    await user.click(screen.getByRole('button', { name: /^Edit$/ }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Front'), ' more words')
    expect(screen.getByText('Question')).toBeInTheDocument()
    expect(screen.queryByText('Answer')).not.toBeInTheDocument()
  })

  it('add card posts the week and shows the 409 as "Upload a lecture for this week first"', async () => {
    const user = userEvent.setup()
    vi.mocked(assetsApi.flashcards).mockResolvedValue([card()])
    const conflict = new AppApiError('no_source_artifact', 409)
    conflict.code = 'no_source_artifact'
    vi.mocked(assetsApi.createFlashcard).mockRejectedValue(conflict)
    renderUi(<FlashcardsTab courseCode="CSIT302" week={3} />)
    await screen.findByText('What is a stack?')
    await user.click(screen.getByRole('button', { name: 'Add card' }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Front'), 'Q')
    await user.type(within(dialog).getByLabelText('Back'), 'A')
    await user.click(within(dialog).getByRole('button', { name: 'Add card' }))
    await waitFor(() =>
      expect(assetsApi.createFlashcard).toHaveBeenCalledWith({ course_code: 'CSIT302', week: 3, front: 'Q', back: 'A' }),
    )
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('Upload a lecture for this week first')
    // The dialog stays open so the text is not lost.
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('shows a server 422 message inside the editor', async () => {
    const user = userEvent.setup()
    vi.mocked(assetsApi.flashcards).mockResolvedValue([card()])
    const err = new ValidationError('bad', 422)
    err.fields = { front: 'front is too long' }
    vi.mocked(assetsApi.updateFlashcard).mockRejectedValue(err)
    renderUi(<FlashcardsTab courseCode="CSIT302" week={3} />)
    await screen.findByText('What is a stack?')
    await user.click(screen.getByRole('button', { name: /^Edit$/ }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Back'), '!')
    await user.click(within(dialog).getByRole('button', { name: 'Save changes' }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('front is too long')
  })

  it('offers Add card from the empty state', async () => {
    vi.mocked(assetsApi.flashcards).mockResolvedValue([])
    renderUi(<FlashcardsTab courseCode="CSIT302" week={3} />)
    expect(await screen.findByRole('button', { name: 'Add card' })).toBeInTheDocument()
  })

  it('shows a Practice badge for targeted cards, not Yours', async () => {
    vi.mocked(assetsApi.flashcards).mockResolvedValue([card({ origin: 'targeted' })])
    renderUi(<FlashcardsTab courseCode="CSIT302" week={3} />)
    await screen.findByText('What is a stack?')
    expect(screen.getByText('Practice')).toBeInTheDocument()
    expect(screen.queryByText('Yours')).not.toBeInTheDocument()
  })
})

describe('quiz editing', () => {
  beforeEach(() => vi.clearAllMocks())

  it('edits a multiple-choice question, keeping lettered options, and swaps to the new id', async () => {
    const user = userEvent.setup()
    vi.mocked(assetsApi.quiz).mockResolvedValueOnce([mcq()]).mockResolvedValue([
      mcq({ id: 'q2', question: 'Which structure is LIFO?', origin: 'user' }),
    ])
    vi.mocked(assetsApi.updateQuiz).mockResolvedValue(mcq({ id: 'q2', question: 'Which structure is LIFO?', origin: 'user' }))
    renderUi(<QuizTab courseCode="CSIT302" week={3} />)
    await screen.findByText('Which is LIFO?')

    await user.click(screen.getByRole('button', { name: /^Edit$/ }))
    const dialog = await screen.findByRole('dialog')
    // The existing correct option is pre-selected.
    expect(within(dialog).getByRole('radio', { name: 'Option 2 is correct' })).toBeChecked()
    const q = within(dialog).getByLabelText('Question')
    await user.clear(q)
    await user.type(q, 'Which structure is LIFO?')
    await user.click(within(dialog).getByRole('button', { name: 'Save changes' }))

    await waitFor(() =>
      expect(assetsApi.updateQuiz).toHaveBeenCalledWith('q1', {
        question: 'Which structure is LIFO?',
        options: ['A. Queue', 'B. Stack'],
        correct_answer: 'B',
        explanation: 'Stack pops the newest.',
      }),
    )
    expect(await screen.findByText('Which structure is LIFO?')).toBeInTheDocument()
    expect(screen.getByText('Yours')).toBeInTheDocument()
  })

  it('blocks a multiple-choice question without a marked correct option', async () => {
    const user = userEvent.setup()
    vi.mocked(assetsApi.quiz).mockResolvedValue([mcq()])
    renderUi(<QuizTab courseCode="CSIT302" week={3} />)
    await screen.findByText('Which is LIFO?')
    await user.click(screen.getByRole('button', { name: 'Add question' }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Question'), 'New one?')
    await user.type(within(dialog).getByLabelText('Option 1'), 'x')
    await user.type(within(dialog).getByLabelText('Option 2'), 'y')
    await user.click(within(dialog).getByRole('button', { name: 'Add question' }))
    expect(await within(dialog).findByText('Mark the correct option')).toBeInTheDocument()
    expect(assetsApi.createQuiz).not.toHaveBeenCalled()
  })

  it('adds a short-answer question', async () => {
    const user = userEvent.setup()
    vi.mocked(assetsApi.quiz).mockResolvedValue([mcq()])
    vi.mocked(assetsApi.createQuiz).mockResolvedValue(mcq({ id: 'q3', question_type: 'short_answer', options_json: null, origin: 'user' }))
    renderUi(<QuizTab courseCode="CSIT302" week={3} />)
    await screen.findByText('Which is LIFO?')
    await user.click(screen.getByRole('button', { name: 'Add question' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('radio', { name: 'Short answer' }))
    await user.type(within(dialog).getByLabelText('Question'), 'Define a heap')
    await user.type(within(dialog).getByLabelText('Model answer'), 'A tree with the heap property')
    await user.click(within(dialog).getByRole('button', { name: 'Add question' }))
    await waitFor(() =>
      expect(assetsApi.createQuiz).toHaveBeenCalledWith({
        course_code: 'CSIT302',
        week: 3,
        question_type: 'short_answer',
        question: 'Define a heap',
        correct_answer: 'A tree with the heap property',
      }),
    )
  })

  it('shows the 409 no-lecture message when adding to a week without a lecture', async () => {
    const user = userEvent.setup()
    vi.mocked(assetsApi.quiz).mockResolvedValue([])
    const conflict = new AppApiError('no_source_artifact', 409)
    vi.mocked(assetsApi.createQuiz).mockRejectedValue(conflict)
    renderUi(<QuizTab courseCode="CSIT302" week={3} />)
    await user.click(await screen.findByRole('button', { name: 'Add question' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('radio', { name: 'Short answer' }))
    await user.type(within(dialog).getByLabelText('Question'), 'Q?')
    await user.type(within(dialog).getByLabelText('Model answer'), 'A')
    await user.click(within(dialog).getByRole('button', { name: 'Add question' }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('Upload a lecture for this week first')
  })

  it('delete confirms first, then calls the API with the question id', async () => {
    const user = userEvent.setup()
    vi.mocked(assetsApi.quiz).mockResolvedValueOnce([mcq()]).mockResolvedValue([])
    vi.mocked(assetsApi.deleteQuiz).mockResolvedValue(undefined)
    renderUi(<QuizTab courseCode="CSIT302" week={3} />)
    await screen.findByText('Which is LIFO?')
    await user.click(screen.getByRole('button', { name: /^Delete$/ }))
    const dialog = await screen.findByRole('dialog')
    expect(assetsApi.deleteQuiz).not.toHaveBeenCalled()
    await user.click(within(dialog).getByRole('button', { name: 'Delete' }))
    await waitFor(() => expect(assetsApi.deleteQuiz).toHaveBeenCalledWith('q1'))
    expect(await screen.findByText('No quiz questions yet')).toBeInTheDocument()
  })

  it('keeps the Practice badge for targeted questions', async () => {
    vi.mocked(assetsApi.quiz).mockResolvedValue([mcq({ origin: 'targeted' })])
    renderUi(<QuizTab courseCode="CSIT302" week={3} />)
    await screen.findByText('Which is LIFO?')
    expect(screen.getByText('Practice')).toBeInTheDocument()
  })
})
