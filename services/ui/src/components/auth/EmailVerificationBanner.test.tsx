import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { RateLimitError } from '../../api/errors'
import { authApi } from '../../api/auth'
import { EmailVerificationBanner } from './EmailVerificationBanner'

vi.mock('../../api/auth', () => ({
  authApi: {
    resendVerification: vi.fn(),
  },
}))

const mockedResend = vi.mocked(authApi.resendVerification)

const mockUseAuth = vi.fn()
vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}))

function renderBanner() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  return render(<EmailVerificationBanner />, { wrapper })
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

describe('EmailVerificationBanner', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedResend.mockResolvedValue({ detail: 'Verification email sent' })
  })

  it('renders a resend prompt for an unverified user', () => {
    mockUseAuth.mockReturnValue({ user: makeUser(), isDemo: false })
    renderBanner()

    expect(screen.getByText(/your email isn't verified yet/i)).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /resend verification email/i }),
    ).toBeInTheDocument()
  })

  it('renders nothing for a verified user', () => {
    mockUseAuth.mockReturnValue({ user: makeUser({ email_verified: true }), isDemo: false })
    const { container } = renderBanner()

    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing for an anonymous session', () => {
    mockUseAuth.mockReturnValue({ user: null, isDemo: false })
    const { container } = renderBanner()

    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing for the demo account', () => {
    mockUseAuth.mockReturnValue({ user: makeUser({ role: 'demo' }), isDemo: true })
    const { container } = renderBanner()

    expect(container).toBeEmptyDOMElement()
  })

  it('sends a resend request and confirms it', async () => {
    mockUseAuth.mockReturnValue({ user: makeUser(), isDemo: false })
    renderBanner()

    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: /resend verification email/i }))

    await waitFor(() => {
      expect(mockedResend).toHaveBeenCalledTimes(1)
    })
    expect(await screen.findByText(/verification email sent/i)).toBeInTheDocument()
  })

  it('surfaces a rate-limit notice instead of failing silently', async () => {
    const err = new RateLimitError('Too many requests', 429)
    err.retryAfterSeconds = 60
    mockedResend.mockRejectedValueOnce(err)
    mockUseAuth.mockReturnValue({ user: makeUser(), isDemo: false })
    renderBanner()

    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: /resend verification email/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/too many attempts/i)
    expect(
      screen.getByRole('button', { name: /resend verification email/i }),
    ).toBeDisabled()
  })

  it('can be dismissed', async () => {
    mockUseAuth.mockReturnValue({ user: makeUser(), isDemo: false })
    renderBanner()

    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: /dismiss verification notice/i }))

    expect(screen.queryByText(/your email isn't verified yet/i)).not.toBeInTheDocument()
  })
})
