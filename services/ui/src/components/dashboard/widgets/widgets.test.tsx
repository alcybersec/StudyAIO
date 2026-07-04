import { useState } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { StreakWidget } from './StreakWidget'
import { ExamsWidget } from './ExamsWidget'
import { useDashboardExams, useDashboardStreak } from '../../../hooks/useApi'

vi.mock('../../../hooks/useApi', () => ({
  useDashboardStreak: vi.fn(),
  useDashboardExams: vi.fn(),
}))

const mockStreak = vi.mocked(useDashboardStreak)
const mockExams = vi.mocked(useDashboardExams)

type QueryShape = { data: unknown; isLoading: boolean; isError: boolean; refetch: () => void }
const asResult = (q: QueryShape) => q as unknown as ReturnType<typeof useDashboardStreak> & ReturnType<typeof useDashboardExams>

const streakData = { current_streak: 12, longest_streak: 15, last_study_date: '2026-07-03' }

function renderWidgets(ui: React.ReactNode) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('per-widget error isolation', () => {
  it('renders ErrorState in the failing widget while the sibling renders data', () => {
    mockExams.mockReturnValue(asResult({ data: undefined, isLoading: false, isError: true, refetch: vi.fn() }))
    mockStreak.mockReturnValue(asResult({ data: streakData, isLoading: false, isError: false, refetch: vi.fn() }))

    renderWidgets(
      <>
        <ExamsWidget />
        <StreakWidget />
      </>,
    )

    // The exams widget failed alone…
    const alert = screen.getByRole('alert')
    expect(within(alert).getByText(/active exams couldn't load/i)).toBeInTheDocument()
    // …while the streak widget keeps working.
    expect(screen.getByText(/12 days/i)).toBeInTheDocument()
    expect(screen.getAllByRole('alert')).toHaveLength(1)
  })

  it('retry button refetches only the failing widget query', async () => {
    const user = userEvent.setup()
    const refetchExams = vi.fn()
    const refetchStreak = vi.fn()
    mockExams.mockReturnValue(asResult({ data: undefined, isLoading: false, isError: true, refetch: refetchExams }))
    mockStreak.mockReturnValue(asResult({ data: streakData, isLoading: false, isError: false, refetch: refetchStreak }))

    renderWidgets(
      <>
        <ExamsWidget />
        <StreakWidget />
      </>,
    )

    await user.click(screen.getByRole('button', { name: /retry/i }))
    expect(refetchExams).toHaveBeenCalledTimes(1)
    expect(refetchStreak).not.toHaveBeenCalled()
  })

  it('renders cached data even when a background refetch errored (offline)', () => {
    mockStreak.mockReturnValue(asResult({ data: streakData, isLoading: false, isError: true, refetch: vi.fn() }))

    renderWidgets(<StreakWidget />)

    expect(screen.getByText(/12 days/i)).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('renders an actionable EmptyState when the slice is empty', () => {
    mockExams.mockReturnValue(asResult({ data: [], isLoading: false, isError: false, refetch: vi.fn() }))

    renderWidgets(<ExamsWidget />)

    expect(screen.getByText(/no exams tracked/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /go to exams/i })).toHaveAttribute('href', '/study?tab=exams')
  })

  it('renders a skeleton while loading', () => {
    mockStreak.mockReturnValue(asResult({ data: undefined, isLoading: true, isError: false, refetch: vi.fn() }))

    renderWidgets(<StreakWidget />)

    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.queryByText(/12 days/i)).not.toBeInTheDocument()
  })
})

describe('widget memoization', () => {
  function Parent() {
    const [, setTick] = useState(0)
    return (
      <>
        <button onClick={() => setTick((t) => t + 1)}>bump</button>
        <StreakWidget />
      </>
    )
  }

  it('a parent re-render does not re-render the memoized widget', async () => {
    const user = userEvent.setup()
    mockStreak.mockReturnValue(asResult({ data: streakData, isLoading: false, isError: false, refetch: vi.fn() }))

    renderWidgets(<Parent />)
    expect(mockStreak).toHaveBeenCalledTimes(1)

    await user.click(screen.getByRole('button', { name: 'bump' }))
    // React.memo with no props: the widget body (and its hook) must not run again.
    expect(mockStreak).toHaveBeenCalledTimes(1)
  })
})
