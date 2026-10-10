import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { LeaderboardPrivacyCard } from './LeaderboardPrivacyCard'
import { useSettings, useUpdateSettings } from '../../../hooks/useApi'

vi.mock('../../../hooks/useApi', () => ({
  useSettings: vi.fn(),
  useUpdateSettings: vi.fn(),
}))

const mockSettings = vi.mocked(useSettings)
const mockUpdate = vi.mocked(useUpdateSettings)
const asResult = (q: object) => q as never
const mutate = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
  mockUpdate.mockReturnValue(asResult({ mutate, isPending: false }))
})

describe('LeaderboardPrivacyCard', () => {
  it('is off by default and states so', () => {
    mockSettings.mockReturnValue(asResult({ data: { leaderboard_opt_in: false }, isLoading: false, isError: false }))
    render(<LeaderboardPrivacyCard />)
    expect(screen.getByRole('switch', { name: /show me on the leaderboard/i })).not.toBeChecked()
    expect(screen.getByText(/off by default/i)).toBeInTheDocument()
  })

  it('sends leaderboard_opt_in: true when toggled on', async () => {
    mockSettings.mockReturnValue(asResult({ data: { leaderboard_opt_in: false }, isLoading: false, isError: false }))
    render(<LeaderboardPrivacyCard />)
    await userEvent.setup().click(screen.getByRole('switch', { name: /show me on the leaderboard/i }))
    expect(mutate).toHaveBeenCalledWith({ leaderboard_opt_in: true }, expect.anything())
  })

  it('sends leaderboard_opt_in: false when toggled off', async () => {
    mockSettings.mockReturnValue(asResult({ data: { leaderboard_opt_in: true }, isLoading: false, isError: false }))
    render(<LeaderboardPrivacyCard />)
    const sw = screen.getByRole('switch', { name: /show me on the leaderboard/i })
    expect(sw).toBeChecked()
    await userEvent.setup().click(sw)
    expect(mutate).toHaveBeenCalledWith({ leaderboard_opt_in: false }, expect.anything())
  })

  it('disables the switch and shows saving state while the mutation is pending', () => {
    mockSettings.mockReturnValue(asResult({ data: { leaderboard_opt_in: false }, isLoading: false, isError: false }))
    mockUpdate.mockReturnValue(asResult({ mutate, isPending: true }))
    render(<LeaderboardPrivacyCard />)
    expect(screen.getByRole('switch')).toBeDisabled()
    expect(screen.getByRole('status')).toHaveTextContent(/saving/i)
  })

  it('shows an error and no switch when settings fail to load', () => {
    mockSettings.mockReturnValue(asResult({ data: undefined, isLoading: false, isError: true }))
    render(<LeaderboardPrivacyCard />)
    expect(screen.getByRole('alert')).toHaveTextContent(/couldn't load/i)
    expect(screen.queryByRole('switch')).not.toBeInTheDocument()
  })
})
