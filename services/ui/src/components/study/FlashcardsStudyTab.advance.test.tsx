import { MemoryRouter } from 'react-router-dom'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { FlashcardsStudyTab } from './FlashcardsStudyTab'
import { studyApi } from '../../api/endpoints'
import { aiFeedbackApi } from '../../api/aiFeedback'
import type { Flashcard } from '../../types'

vi.mock('../../api/endpoints', () => ({
  studyApi: { due: vi.fn(), review: vi.fn() },
  examsApi: { recordSession: vi.fn(), get: vi.fn() },
}))
vi.mock('../../api/aiFeedback', () => ({
  aiFeedbackApi: { mine: vi.fn(), put: vi.fn(), clear: vi.fn() },
}))
vi.mock('sonner', () => ({ toast: { error: vi.fn(), info: vi.fn() } }))

const card = (n: number): Flashcard => ({
  id: `card-${n}`,
  course_id: 'c1',
  week: 1,
  front: `Front ${n}`,
  back: `Back ${n}`,
  tags: [],
  source_artifact_id: 'a1',
  source_page_ref: 0,
  generation_version: 1,
  created_at: '2026-10-15T00:00:00Z',
})

/** A server-side due list: rating a card removes it, like the real endpoint. */
let due: Flashcard[]

beforeEach(() => {
  vi.clearAllMocks()
  due = [card(1), card(2), card(3)]
  vi.mocked(studyApi.due).mockImplementation(async () => [...due])
  vi.mocked(studyApi.review).mockImplementation((async (req: { flashcard_id: string }) => {
    due = due.filter((c) => c.id !== req.flashcard_id)
    return {}
  }) as never)
  vi.mocked(aiFeedbackApi.mine).mockResolvedValue([])
})

async function rateGood() {
  await userEvent.click(screen.getByRole('button', { name: /Showing question/ }))
  await userEvent.click(screen.getByRole('button', { name: /^Good/ }))
}

describe('flashcard runner advancing', () => {
  it('shows every due card once even though the due list shrinks after each rating', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={['/study?exam=e1&course=C1']}>
          <FlashcardsStudyTab />
        </MemoryRouter>
      </QueryClientProvider>,
    )
    expect(await screen.findByText('Front 1')).toBeInTheDocument()
    await rateGood()
    expect(await screen.findByText('Front 2')).toBeInTheDocument()
    expect(screen.getByText(/Card 2 of 3/)).toBeInTheDocument()
    await rateGood()
    expect(await screen.findByText('Front 3')).toBeInTheDocument()
    expect(studyApi.review).toHaveBeenCalledTimes(2)
  })
})
