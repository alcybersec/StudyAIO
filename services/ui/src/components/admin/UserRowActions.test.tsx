import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { UserRowActions } from './UserRowActions'
import {
  useClearUserMfa,
  useDeleteAdminUser,
  useResendVerification,
  useSendPasswordReset,
  useUpdateAdminUser,
} from '../../hooks/useApi'

vi.mock('../../hooks/useApi', () => ({
  useClearUserMfa: vi.fn(),
  useDeleteAdminUser: vi.fn(),
  useResendVerification: vi.fn(),
  useSendPasswordReset: vi.fn(),
  useUpdateAdminUser: vi.fn(),
}))

const asResult = (q: object) => q as never
const resetMutate = vi.fn()
const verifyMutate = vi.fn()
const deleteMutate = vi.fn()
const clearMfaMutate = vi.fn()
const updateMutate = vi.fn()

const USER = {
  id: 'u-1',
  email: 'tester@example.com',
  username: 'tester',
  role: 'user',
  tier: 'free',
  is_active: true,
  created_at: null,
  last_login_at: null,
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(useSendPasswordReset).mockReturnValue(asResult({ mutate: resetMutate, isPending: false }))
  vi.mocked(useResendVerification).mockReturnValue(
    asResult({ mutate: verifyMutate, isPending: false }),
  )
  vi.mocked(useDeleteAdminUser).mockReturnValue(asResult({ mutate: deleteMutate, isPending: false }))
  vi.mocked(useClearUserMfa).mockReturnValue(asResult({ mutate: clearMfaMutate, isPending: false }))
  vi.mocked(useUpdateAdminUser).mockReturnValue(asResult({ mutate: updateMutate, isPending: false }))
})

function setup(currentUserId: string | undefined = 'admin-001') {
  render(<UserRowActions user={USER} currentUserId={currentUserId} />)
  return userEvent.setup()
}

describe('UserRowActions', () => {
  it('sends a password reset', async () => {
    const user = setup()
    await user.click(screen.getByRole('button', { name: /send password reset/i }))
    expect(resetMutate).toHaveBeenCalledWith('u-1', expect.anything())
  })

  it('resends verification', async () => {
    const user = setup()
    await user.click(screen.getByRole('button', { name: /resend verification/i }))
    expect(verifyMutate).toHaveBeenCalledWith('u-1', expect.anything())
  })

  it('does not delete on the first click', async () => {
    const user = setup()
    await user.click(screen.getByRole('button', { name: /delete tester@example.com/i }))
    expect(deleteMutate).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: /confirm/i })).toBeInTheDocument()
  })

  it('deletes once confirmed', async () => {
    const user = setup()
    await user.click(screen.getByRole('button', { name: /delete tester@example.com/i }))
    await user.click(screen.getByRole('button', { name: /confirm/i }))
    expect(deleteMutate).toHaveBeenCalledWith('u-1', expect.anything())
  })

  it('can back out of a delete', async () => {
    const user = setup()
    await user.click(screen.getByRole('button', { name: /delete tester@example.com/i }))
    await user.click(screen.getByRole('button', { name: /cancel/i }))
    expect(deleteMutate).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: /delete tester@example.com/i })).toBeInTheDocument()
  })

  it('will not let an admin delete themselves from here', () => {
    setup('u-1')
    expect(screen.getByRole('button', { name: /delete tester@example.com/i })).toBeDisabled()
  })
})

// ── Change email ───────────────────────────────────────────────
//
// The destructive half of issue #60. A PATCH carrying `email` revokes the
// user's sessions, unlinks every OAuth identity, voids unused magic links and
// clears email_verified, so nothing here may reach `updateUser.mutate` without
// the operator having read that list and typed the address twice.

const NEW_ADDRESS = 'moved@example.com'

async function openEmailDialog(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: /change email for tester@example\.com/i }))
  return screen.getByRole('dialog')
}

describe('UserRowActions: change email', () => {
  it('sends nothing when the dialog merely opens', async () => {
    const user = setup()
    await openEmailDialog(user)
    expect(updateMutate).not.toHaveBeenCalled()
  })

  it('names the consequences, including the re-link that is not automatic', async () => {
    const user = setup()
    const dialog = await openEmailDialog(user)

    expect(dialog).toHaveTextContent(/signs tester@example\.com out on every device/i)
    expect(dialog).toHaveTextContent(/7-day refresh token/i)
    expect(dialog).toHaveTextContent(/unlinks every connected sign-in provider/i)
    // The one consequence the admin cannot clean up afterwards.
    expect(dialog).toHaveTextContent(/re-linking is not automatic/i)
    expect(dialog).toHaveTextContent(/voids every unused link already sent to the old address/i)
    expect(dialog).toHaveTextContent(/unverified/i)
    expect(dialog).toHaveTextContent(/already belongs to another account/i)
  })

  it('will not submit until the new address is typed twice and matches', async () => {
    const user = setup()
    await openEmailDialog(user)
    const submit = screen.getByRole('button', { name: /change email and sign them out/i })

    expect(submit).toBeDisabled()

    await user.type(screen.getByLabelText(/new email address/i), NEW_ADDRESS)
    expect(submit).toBeDisabled()

    await user.type(screen.getByLabelText(/type the new address again/i), 'moved@exmaple.com')
    expect(screen.getByText(/do not match/i)).toBeInTheDocument()
    expect(submit).toBeDisabled()
    expect(updateMutate).not.toHaveBeenCalled()
  })

  it('refuses a case-only change rather than promising consequences that will not happen', async () => {
    // Since #91 the server normalises, so this is a genuine no-op there: no
    // sign-out, no unlink. The dialog must not offer to do it.
    const user = setup()
    await openEmailDialog(user)

    await user.type(screen.getByLabelText(/new email address/i), ' Tester@Example.COM ')
    await user.type(screen.getByLabelText(/type the new address again/i), ' Tester@Example.COM ')

    expect(screen.getByText(/already this account/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /change email and sign them out/i })).toBeDisabled()
    expect(updateMutate).not.toHaveBeenCalled()
  })

  it('cancelling sends nothing', async () => {
    const user = setup()
    await openEmailDialog(user)
    await user.type(screen.getByLabelText(/new email address/i), NEW_ADDRESS)
    await user.type(screen.getByLabelText(/type the new address again/i), NEW_ADDRESS)
    await user.click(screen.getByRole('button', { name: /cancel/i }))

    expect(updateMutate).not.toHaveBeenCalled()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('PATCHes the normalised address on confirm', async () => {
    const user = setup()
    await openEmailDialog(user)
    await user.type(screen.getByLabelText(/new email address/i), ` ${NEW_ADDRESS.toUpperCase()} `)
    await user.type(screen.getByLabelText(/type the new address again/i), NEW_ADDRESS)
    await user.click(screen.getByRole('button', { name: /change email and sign them out/i }))

    expect(updateMutate).toHaveBeenCalledWith(
      { userId: 'u-1', data: { email: NEW_ADDRESS } },
      expect.anything(),
    )
  })

  it('offers the verification link the change makes necessary', async () => {
    updateMutate.mockImplementation(
      (_vars: unknown, opts: { onSuccess?: () => void }) => opts.onSuccess?.(),
    )
    const user = setup()
    await openEmailDialog(user)
    await user.type(screen.getByLabelText(/new email address/i), NEW_ADDRESS)
    await user.type(screen.getByLabelText(/type the new address again/i), NEW_ADDRESS)
    await user.click(screen.getByRole('button', { name: /change email and sign them out/i }))

    await user.click(screen.getByRole('button', { name: /send verification link/i }))
    expect(verifyMutate).toHaveBeenCalledWith('u-1', expect.anything())
  })
})

// ── Clear MFA ──────────────────────────────────────────────────

describe('UserRowActions: clear MFA', () => {
  it('asks first, and says what clearing MFA costs', async () => {
    const user = setup()
    await user.click(screen.getByRole('button', { name: /clear mfa for tester@example\.com/i }))

    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveTextContent(/out of band/i)
    expect(dialog).toHaveTextContent(/signs tester@example\.com out on every device/i)
    expect(clearMfaMutate).not.toHaveBeenCalled()
  })

  it('cancelling clears nothing', async () => {
    const user = setup()
    await user.click(screen.getByRole('button', { name: /clear mfa for tester@example\.com/i }))
    await user.click(screen.getByRole('button', { name: /cancel/i }))

    expect(clearMfaMutate).not.toHaveBeenCalled()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('calls the mfa-reset mutation once confirmed', async () => {
    const user = setup()
    await user.click(screen.getByRole('button', { name: /clear mfa for tester@example\.com/i }))
    await user.click(screen.getByRole('button', { name: /^clear mfa$/i }))

    expect(clearMfaMutate).toHaveBeenCalledWith('u-1', expect.anything())
  })
})
