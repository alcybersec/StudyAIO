import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { AppApiError, NetworkError } from '../api/errors'
import { authApi } from '../api/auth'
import { VerifyEmailPage } from './VerifyEmailPage'

vi.mock('../api/auth', () => ({
  authApi: {
    verifyEmail: vi.fn(),
    resendVerification: vi.fn(),
  },
}))

const mockedVerify = vi.mocked(authApi.verifyEmail)
const mockedResend = vi.mocked(authApi.resendVerification)

const mockUseAuth = vi.fn()
vi.mock('../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}))

function renderPage(route = '/verify-email?token=tok-123') {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>
    </QueryClientProvider>
  )
  return render(<VerifyEmailPage />, { wrapper })
}

function makeUser(overrides: Record<string, unknown> = {}) {
  return {
    id: 'u1',
    email: 'alex@example.com',
    username: 'alex',
    role: 'user',
    tier: 'free',
    is_active: true,
    email_verified: false,
    mfa_enabled: false,
    avatar_url: null,
    last_login_at: null,
    created_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

describe('VerifyEmailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedVerify.mockResolvedValue({ detail: 'Email verified' })
    mockUseAuth.mockReturnValue({ user: null, isDemo: false })
  })

  it('posts the token once on mount and reports success', async () => {
    renderPage()

    expect(await screen.findByText('Email verified!')).toBeInTheDocument()
    expect(mockedVerify).toHaveBeenCalledTimes(1)
    expect(mockedVerify).toHaveBeenCalledWith({ token: 'tok-123' })
    expect(screen.getByRole('link', { name: /go to dashboard/i })).toHaveAttribute(
      'href',
      '/',
    )
  })

  it('shows a failure state when the token is rejected', async () => {
    mockedVerify.mockRejectedValueOnce(new AppApiError('Invalid verification token', 401))
    renderPage()

    expect(
      await screen.findByText(/this verification link is invalid or has expired/i),
    ).toBeInTheDocument()
  })

  it('does not call the API when the token is missing', async () => {
    renderPage('/verify-email')

    expect(
      await screen.findByText(/this verification link is invalid or has expired/i),
    ).toBeInTheDocument()
    expect(mockedVerify).not.toHaveBeenCalled()
  })

  it('offers a retry when the server is unreachable', async () => {
    mockedVerify.mockRejectedValueOnce(new NetworkError())
    renderPage()

    expect(await screen.findByText(/couldn't reach the server/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })

  it('offers a resend to a logged-in unverified user after failure', async () => {
    mockedVerify.mockRejectedValueOnce(new AppApiError('Invalid verification token', 401))
    mockedResend.mockResolvedValue({ detail: 'Verification email sent' })
    mockUseAuth.mockReturnValue({ user: makeUser(), isDemo: false })
    renderPage()

    const resendButton = await screen.findByRole('button', {
      name: /resend verification email/i,
    })
    const user = userEvent.setup()
    await user.click(resendButton)

    await waitFor(() => {
      expect(mockedResend).toHaveBeenCalledTimes(1)
    })
    expect(await screen.findByText(/verification email sent/i)).toBeInTheDocument()
  })

  it('hides the resend button when the user is already verified', async () => {
    mockedVerify.mockRejectedValueOnce(new AppApiError('Invalid verification token', 401))
    mockUseAuth.mockReturnValue({ user: makeUser({ email_verified: true }), isDemo: false })
    renderPage()

    await screen.findByText(/this verification link is invalid or has expired/i)
    expect(
      screen.queryByRole('button', { name: /resend verification email/i }),
    ).not.toBeInTheDocument()
  })
})
