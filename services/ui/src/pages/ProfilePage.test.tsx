import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ApiError } from '../api/client'
import { ProfilePage } from './ProfilePage'

const changePassword = vi.fn()
const endSession = vi.fn()

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => ({
    user: {
      id: 'user-1',
      email: 'alex@example.com',
      username: 'alex',
      avatar_url: null,
      mfa_enabled: false,
    },
  }),
  useUpdateProfile: () => ({ mutateAsync: vi.fn(), isPending: false, isError: false }),
  useChangePassword: () => ({ mutateAsync: changePassword, isPending: false }),
  useSessionHandoff: () => endSession,
  useMFASetup: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useMFAVerify: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useMFADisable: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

async function submitPasswordChange() {
  const user = userEvent.setup()
  await user.type(screen.getByLabelText(/current password/i), 'OldPass1!')
  await user.type(screen.getByLabelText(/^new password$/i), 'NewPass1!')
  await user.type(screen.getByLabelText(/confirm new password/i), 'NewPass1!')
  await user.click(screen.getByRole('button', { name: /change password/i }))
}

function setup() {
  render(
    <MemoryRouter initialEntries={['/profile']}>
      <ProfilePage />
    </MemoryRouter>,
  )
}

describe('ProfilePage password change', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('hands the user off to login when the server ended the session', async () => {
    changePassword.mockResolvedValueOnce({ detail: 'Password changed', session_ended: true })
    setup()
    await submitPasswordChange()

    expect(changePassword).toHaveBeenCalledWith({
      old_password: 'OldPass1!',
      new_password: 'NewPass1!',
    })
    expect(endSession).toHaveBeenCalledWith('password_changed')
    // No lingering success state — the user is on their way to /login.
    expect(screen.queryByText('Password changed')).not.toBeInTheDocument()
  })

  it('keeps the user in place when the session survived', async () => {
    changePassword.mockResolvedValueOnce({ detail: 'Password changed', session_ended: false })
    setup()
    await submitPasswordChange()

    expect(endSession).not.toHaveBeenCalled()
    expect(await screen.findByText('Password changed')).toBeInTheDocument()
  })

  it('does not sign the user out when the change is rejected', async () => {
    changePassword.mockRejectedValueOnce(new ApiError('Current password is incorrect', 401))
    setup()
    await submitPasswordChange()

    expect(endSession).not.toHaveBeenCalled()
    expect(await screen.findByText('Current password is incorrect')).toBeInTheDocument()
  })

  it('rejects a mismatched confirmation without calling the API', async () => {
    setup()
    const user = userEvent.setup()
    await user.type(screen.getByLabelText(/current password/i), 'OldPass1!')
    await user.type(screen.getByLabelText(/^new password$/i), 'NewPass1!')
    await user.type(screen.getByLabelText(/confirm new password/i), 'Different1!')
    await user.click(screen.getByRole('button', { name: /change password/i }))

    expect(changePassword).not.toHaveBeenCalled()
    expect(endSession).not.toHaveBeenCalled()
  })
})
