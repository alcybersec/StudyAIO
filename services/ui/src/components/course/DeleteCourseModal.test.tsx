import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { DeleteCourseModal } from './DeleteCourseModal'
import type { Course, WeekSummaryRow } from '../../types'

const removeMock = vi.fn()
const archiveMock = vi.fn()

vi.mock('../../api/endpoints', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/endpoints')>()
  return {
    ...actual,
    coursesApi: {
      ...actual.coursesApi,
      remove: (code: string) => removeMock(code),
      archive: (code: string) => archiveMock(code),
    },
  }
})

const course: Course = {
  id: 'c1',
  code: 'CSIT302',
  name: 'Cybersecurity',
  term: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const weeks: WeekSummaryRow[] = [
  {
    week: 1,
    titles: ['Intro'],
    artifact_count: 2,
    summary_status: 'completed',
    summary_id: 's1',
    flashcard_count: 10,
    quiz_count: 5,
  },
  {
    week: 2,
    titles: ['Crypto'],
    artifact_count: 1,
    summary_status: 'completed',
    summary_id: 's2',
    flashcard_count: 8,
    quiz_count: 3,
  },
]

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <DeleteCourseModal open onOpenChange={() => {}} course={course} weeks={weeks} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  removeMock.mockResolvedValue({ code: 'CSIT302', deleted: true, counts: {} })
  archiveMock.mockResolvedValue({ code: 'CSIT302', archived: true })
})

describe('DeleteCourseModal', () => {
  it('shows real consequence counts built from course stats', () => {
    setup()
    expect(screen.getByText(/2 weeks of summaries/i)).toBeInTheDocument()
    expect(screen.getByText(/18 flashcards/i)).toBeInTheDocument()
    expect(screen.getByText(/8 quiz questions/i)).toBeInTheDocument()
    expect(screen.getByText(/3 uploaded source files/i)).toBeInTheDocument()
  })

  it('keeps the delete button disabled until the typed code matches', async () => {
    const user = userEvent.setup()
    setup()

    const deleteButton = screen.getByRole('button', { name: /delete permanently/i })
    expect(deleteButton).toBeDisabled()

    const input = screen.getByLabelText(/type "CSIT302" to confirm/i)
    await user.type(input, 'CSIT30')
    expect(deleteButton).toBeDisabled()

    await user.type(input, '2')
    expect(deleteButton).toBeEnabled()

    await user.type(input, 'X')
    expect(deleteButton).toBeDisabled()
  })

  it('calls the delete endpoint with the course code when confirmed', async () => {
    const user = userEvent.setup()
    setup()

    await user.type(screen.getByLabelText(/type "CSIT302" to confirm/i), 'CSIT302')
    await user.click(screen.getByRole('button', { name: /delete permanently/i }))

    expect(removeMock).toHaveBeenCalledWith('CSIT302')
    expect(archiveMock).not.toHaveBeenCalled()
  })

  it('offers archive as a non-destructive alternative', async () => {
    const user = userEvent.setup()
    setup()

    await user.click(screen.getByRole('button', { name: /archive instead/i }))

    expect(archiveMock).toHaveBeenCalledWith('CSIT302')
    expect(removeMock).not.toHaveBeenCalled()
  })
})
