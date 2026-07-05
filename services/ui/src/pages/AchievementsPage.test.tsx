import { MemoryRouter } from 'react-router-dom'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AchievementsPage } from './AchievementsPage'
import { useAchievements, useLeaderboard, useXPSummary } from '../hooks/useApi'

vi.mock('../hooks/useApi', () => ({
  useAchievements: vi.fn(),
  useLeaderboard: vi.fn(),
  useXPSummary: vi.fn(),
}))

const mockAchievements = vi.mocked(useAchievements)
const mockLeaderboard = vi.mocked(useLeaderboard)
const mockXP = vi.mocked(useXPSummary)

const asResult = (q: object) => q as never

const makeAchievement = (overrides: Record<string, unknown> = {}) => ({
  id: 'a1',
  code: 'first_upload',
  title: 'First Upload',
  description: 'Upload your first lecture',
  icon: 'upload',
  category: 'milestone',
  xp_reward: 10,
  earned: true,
  earned_at: '2026-01-01T00:00:00',
  ...overrides,
})

const xpData = {
  total_xp: 250,
  level: 2,
  progress_pct: 50,
  current_threshold: 100,
  next_threshold: 300,
  recent_events: [],
}

beforeEach(() => {
  vi.clearAllMocks()
  mockLeaderboard.mockReturnValue(asResult({ data: undefined, isLoading: true, isError: false, refetch: vi.fn() }))
})

function renderPage(initialEntries: string[] = ['/achievements']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <AchievementsPage />
    </MemoryRouter>,
  )
}

describe('AchievementsPage section isolation', () => {
  it('shows XP ErrorState while the achievements grid still renders data', () => {
    mockXP.mockReturnValue(asResult({ data: undefined, isLoading: false, isError: true, refetch: vi.fn() }))
    mockAchievements.mockReturnValue(
      asResult({
        data: { total: 1, earned: 1, achievements: [makeAchievement()] },
        isLoading: false,
        isError: false,
        refetch: vi.fn(),
      }),
    )

    renderPage()

    const alert = screen.getByRole('alert')
    expect(within(alert).getByText(/xp progress couldn't load/i)).toBeInTheDocument()
    expect(screen.getByText('First Upload')).toBeInTheDocument()
  })

  it('retries only the XP query from its ErrorState', async () => {
    const user = userEvent.setup()
    const refetchXP = vi.fn()
    const refetchAch = vi.fn()
    mockXP.mockReturnValue(asResult({ data: undefined, isLoading: false, isError: true, refetch: refetchXP }))
    mockAchievements.mockReturnValue(
      asResult({
        data: { total: 1, earned: 1, achievements: [makeAchievement()] },
        isLoading: false,
        isError: false,
        refetch: refetchAch,
      }),
    )

    renderPage()
    await user.click(screen.getByRole('button', { name: /retry/i }))

    expect(refetchXP).toHaveBeenCalledTimes(1)
    expect(refetchAch).not.toHaveBeenCalled()
  })
})

describe('AchievementsPage category filter', () => {
  beforeEach(() => {
    mockXP.mockReturnValue(asResult({ data: xpData, isLoading: false, isError: false, refetch: vi.fn() }))
    mockAchievements.mockReturnValue(
      asResult({
        data: {
          total: 2,
          earned: 1,
          achievements: [
            makeAchievement(),
            makeAchievement({ id: 'a2', title: 'Streak Starter', category: 'streak', earned: false }),
          ],
        },
        isLoading: false,
        isError: false,
        refetch: vi.fn(),
      }),
    )
  })

  it('filters achievements when a category pill is clicked', async () => {
    const user = userEvent.setup()
    renderPage()

    expect(screen.getByText('First Upload')).toBeInTheDocument()
    expect(screen.getByText('Streak Starter')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Streak' }))

    expect(screen.queryByText('First Upload')).not.toBeInTheDocument()
    expect(screen.getByText('Streak Starter')).toBeInTheDocument()
  })

  it('shows a compact empty state when a category has no achievements', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByRole('button', { name: 'Mastery' }))

    expect(screen.getByText(/no achievements in this category/i)).toBeInTheDocument()
  })
})

describe('AchievementsPage leaderboard tab', () => {
  beforeEach(() => {
    mockXP.mockReturnValue(asResult({ data: xpData, isLoading: false, isError: false, refetch: vi.fn() }))
    mockAchievements.mockReturnValue(
      asResult({
        data: { total: 0, earned: 0, achievements: [] },
        isLoading: false,
        isError: false,
        refetch: vi.fn(),
      }),
    )
  })

  it('shows an EmptyState when the leaderboard has no entries', () => {
    mockLeaderboard.mockReturnValue(
      asResult({ data: { entries: [] }, isLoading: false, isError: false, refetch: vi.fn() }),
    )

    renderPage(['/achievements?tab=leaderboard'])
    expect(screen.getByText(/no leaderboard entries yet/i)).toBeInTheDocument()
  })

  it('renders leaderboard entries in a table', () => {
    mockLeaderboard.mockReturnValue(
      asResult({
        data: { entries: [{ user_id: 'u1', username: 'alice', total_xp: 1200, level: 4, rank: 1 }] },
        isLoading: false,
        isError: false,
        refetch: vi.fn(),
      }),
    )

    renderPage(['/achievements?tab=leaderboard'])

    const table = screen.getByRole('table')
    expect(within(table).getByText('alice')).toBeInTheDocument()
    expect(within(table).getByText('1,200')).toBeInTheDocument()
  })
})
