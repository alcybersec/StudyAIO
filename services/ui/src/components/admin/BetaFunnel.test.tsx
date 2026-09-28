import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { BetaFunnel } from './BetaFunnel'
import { useBetaFunnel } from '../../hooks/useApi'
import type { BetaFunnel as BetaFunnelData } from '../../types'

vi.mock('../../hooks/useApi', () => ({ useBetaFunnel: vi.fn() }))

const asResult = (q: object) => q as never

const DATA: BetaFunnelData = {
  invites_issued: 10,
  invites_redeemed: 4,
  registered: 4,
  verified: 3,
  uploaded: 2,
  processed: 1,
  returned: 1,
  active_7d: 1,
  stalled_after_registering: 2,
  excluded_admins: 1,
  excluded_demo: 0,
  include_admins: false,
}

function withData(data: Partial<BetaFunnelData> = {}) {
  vi.mocked(useBetaFunnel).mockReturnValue(
    asResult({ data: { ...DATA, ...data }, isLoading: false, isError: false, refetch: vi.fn() }),
  )
}

beforeEach(() => vi.clearAllMocks())

describe('BetaFunnel', () => {
  it('renders every step', () => {
    withData()
    render(<BetaFunnel />)

    for (const label of ['Invited', 'Registered', 'Verified', 'Uploaded', 'Processed', 'Returned']) {
      expect(screen.getByText(label)).toBeInTheDocument()
    }
  })

  it('calls out the accounts that registered and never uploaded', () => {
    // The most actionable number on the panel, so it gets prose rather than a bar.
    withData()
    render(<BetaFunnel />)

    expect(screen.getByText(/registered without ever uploading/i)).toBeInTheDocument()
  })

  it('says nothing about stalled accounts when there are none', () => {
    withData({ stalled_after_registering: 0 })
    render(<BetaFunnel />)

    expect(screen.queryByText(/registered without ever uploading/i)).not.toBeInTheDocument()
  })

  it('warns that the totals will not match the user count', () => {
    // Otherwise the excluded admin reads as a bug in one of the two panels.
    withData()
    render(<BetaFunnel />)

    expect(screen.getByText(/will not match the user count/i)).toBeInTheDocument()
  })

  it('excludes admins by default and can opt them in', async () => {
    withData()
    render(<BetaFunnel />)
    const user = userEvent.setup()

    expect(vi.mocked(useBetaFunnel)).toHaveBeenLastCalledWith(false)
    await user.click(screen.getByLabelText(/include admins/i))

    expect(vi.mocked(useBetaFunnel)).toHaveBeenLastCalledWith(true)
  })

  it('shows an error state rather than an empty panel', () => {
    vi.mocked(useBetaFunnel).mockReturnValue(
      asResult({ data: undefined, isLoading: false, isError: true, refetch: vi.fn() }),
    )
    render(<BetaFunnel />)

    expect(screen.getByText(/couldn't load/i)).toBeInTheDocument()
  })
})
