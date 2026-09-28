import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ChangeEmailDialog } from './ChangeEmailDialog'
import { useAdminUserDetail, useResendVerification, useUpdateAdminUser } from '../../hooks/useApi'
import type { AdminUser } from '../../types'

vi.mock('../../hooks/useApi', () => ({
  useAdminUserDetail: vi.fn(),
  useResendVerification: vi.fn(),
  useUpdateAdminUser: vi.fn(),
}))

const asResult = (q: object) => q as never

const USER: AdminUser = {
  id: 'u-1',
  email: 'tester@example.com',
  username: 'tester',
  role: 'user',
  tier: 'free',
  is_active: true,
  mfa_enabled: false,
  created_at: null,
  last_login_at: null,
}

/** Only the profile shape the dialog reads matters here. */
function withProviders(oauth_providers: string[] | null | undefined) {
  vi.mocked(useAdminUserDetail).mockReturnValue(
    asResult({
      data: oauth_providers === undefined ? undefined : { profile: { oauth_providers } },
      isLoading: false,
      isError: false,
    }),
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(useUpdateAdminUser).mockReturnValue(asResult({ mutate: vi.fn(), isPending: false }))
  vi.mocked(useResendVerification).mockReturnValue(asResult({ mutate: vi.fn(), isPending: false }))
})

function open() {
  render(<ChangeEmailDialog open onOpenChange={() => {}} user={USER} />)
}

describe('ChangeEmailDialog: what it says it will unlink', () => {
  // GL#3. The warning used to be generic because nothing exposed the linked
  // providers. The three states below are deliberately not interchangeable.

  it('names the single provider it will unlink', () => {
    withProviders(['google'])
    open()

    expect(screen.getByText(/unlinks their Google sign-in/i)).toBeInTheDocument()
  })

  it('names both when two are linked', () => {
    withProviders(['github', 'google'])
    open()

    expect(screen.getByText(/unlinks their GitHub and Google sign-in/i)).toBeInTheDocument()
  })

  it('drops the warning entirely when nothing is linked', () => {
    withProviders([])
    open()

    expect(screen.queryByText(/unlink/i)).not.toBeInTheDocument()
  })

  it('falls back to the generic warning when the lookup failed', () => {
    // `null` is "we do not know", and must not be read as "nothing is linked":
    // claiming a destructive action breaks no links on no evidence is the one
    // failure mode worse than being vague.
    withProviders(null)
    open()

    expect(screen.getByText(/unlinks every connected sign-in provider/i)).toBeInTheDocument()
  })

  it('is generic while the lookup is still in flight', () => {
    withProviders(undefined)
    open()

    expect(screen.getByText(/unlinks every connected sign-in provider/i)).toBeInTheDocument()
  })

  it('does not query while the dialog is closed', () => {
    withProviders(['google'])
    render(<ChangeEmailDialog open={false} onOpenChange={() => {}} user={USER} />)

    expect(vi.mocked(useAdminUserDetail)).toHaveBeenCalledWith(undefined)
  })
})
