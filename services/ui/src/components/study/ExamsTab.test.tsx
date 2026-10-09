import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ExamsTab } from './ExamsTab'

vi.mock('../../hooks/useApi', () => ({
  useExams: () => ({ data: [], isLoading: false, error: null, refetch: vi.fn() }),
  useCourses: () => ({
    data: [
      { id: 'c1', code: 'CSCI369', name: 'Security' },
      { id: 'c2', code: 'CSIT302', name: 'Other' },
    ],
  }),
  useCreateExam: () => ({ mutateAsync: vi.fn(), isPending: false, isError: false }),
}))
vi.mock('../../hooks/useCalendar', () => ({
  useCalendarStatus: () => ({ data: { calendars: [] } }),
  useSyncCalendar: () => ({ mutate: vi.fn(), isPending: false }),
}))

function renderAt(url: string) {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <ExamsTab onSelectExam={vi.fn()} />
    </MemoryRouter>,
  )
}

describe('ExamsTab builder deep link', () => {
  it('opens the builder with course and week preselected', () => {
    renderAt('/study?tab=exams&create=1&course=CSCI369&week=2')
    expect((screen.getByRole('combobox') as HTMLSelectElement).value).toBe('CSCI369')
    expect((screen.getByPlaceholderText('e.g., 1, 2, 3, 4, 5') as HTMLInputElement).value).toBe('2')
  })

  it('does not open the builder without ?create=1', () => {
    renderAt('/study?tab=exams&course=CSCI369')
    expect(screen.queryByRole('combobox')).toBeNull()
  })
})
