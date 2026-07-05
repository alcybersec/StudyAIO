import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { AppApiError, NetworkError, RateLimitError } from '../api/errors'
import { LoginPage } from './LoginPage'

const login = vi.fn()

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => ({
    login,
    authConfig: {
      self_hosted: false,
      registration_enabled: true,
      oauth_providers: [],
      demo_enabled: false,
    },
  }),
}))

const navigate = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => navigate }
})

function setup() {
  render(
    <MemoryRouter initialEntries={['/login']}>
      <LoginPage />
    </MemoryRouter>,
  )
}

async function submitCredentials() {
  const user = userEvent.setup()
  await user.type(screen.getByLabelText(/email/i), 'alex@example.com')
  await user.type(screen.getByLabelText(/^password$/i), 'hunter2boogaloo')
  await user.click(screen.getByRole('button', { name: /sign in/i }))
  return user
}

describe('LoginPage error mapping', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('maps a 401 to a password-field error', async () => {
    login.mockRejectedValueOnce(new AppApiError('Invalid credentials', 401))
    setup()
    await submitCredentials()

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Wrong email or password')
    expect(screen.getByLabelText(/^password$/i)).toHaveAttribute('aria-invalid', 'true')
    expect(navigate).not.toHaveBeenCalled()
  })

  it('shows the MFA field on a 403 MFA challenge', async () => {
    login.mockRejectedValueOnce(new AppApiError('MFA code required', 403))
    setup()
    await submitCredentials()

    expect(await screen.findByLabelText(/mfa code/i)).toBeInTheDocument()
  })

  it('shows the rate-limit countdown card on a 429', async () => {
    const err = new RateLimitError('Too many requests', 429)
    err.retryAfterSeconds = 90
    login.mockRejectedValueOnce(err)
    setup()
    await submitCredentials()

    const status = await screen.findByRole('status')
    expect(status).toHaveTextContent('Too many attempts')
    expect(status).toHaveTextContent('1:30')
    expect(screen.getByRole('button', { name: /sign in/i })).toBeDisabled()
  })

  it('shows a retryable error state on network failure', async () => {
    login.mockRejectedValueOnce(new NetworkError())
    setup()
    await submitCredentials()

    expect(await screen.findByText(/couldn't reach the server/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })

  it('does not call login when the email is invalid', async () => {
    setup()
    const user = userEvent.setup()
    await user.type(screen.getByLabelText(/email/i), 'not-an-email')
    await user.type(screen.getByLabelText(/^password$/i), 'hunter2boogaloo')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    expect(await screen.findByText(/valid email/i)).toBeInTheDocument()
    expect(login).not.toHaveBeenCalled()
  })

  it('navigates home on success', async () => {
    login.mockResolvedValueOnce({ id: 'u1' })
    setup()
    await submitCredentials()
    expect(navigate).toHaveBeenCalledWith('/')
  })
})
