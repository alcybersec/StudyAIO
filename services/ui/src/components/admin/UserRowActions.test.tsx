import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { UserRowActions } from './UserRowActions'
import {
  useDeleteAdminUser,
  useResendVerification,
  useSendPasswordReset,
} from '../../hooks/useApi'

vi.mock('../../hooks/useApi', () => ({
  useDeleteAdminUser: vi.fn(),
  useResendVerification: vi.fn(),
  useSendPasswordReset: vi.fn(),
}))

const asResult = (q: object) => q as never
const resetMutate = vi.fn()
const verifyMutate = vi.fn()
const deleteMutate = vi.fn()

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
