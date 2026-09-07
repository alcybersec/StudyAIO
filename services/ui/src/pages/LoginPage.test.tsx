import { beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { AppApiError, NetworkError, RateLimitError } from '../api/errors'
import { takeBackupCodesRemaining } from '../lib/backupCodeNotice'
import { LoginPage } from './LoginPage'

const login = vi.fn()
const oauthMfaMutate = vi.fn()

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
  useOAuthMFA: () => ({ mutateAsync: oauthMfaMutate }),
}))

/**
 * Shape placeholder, not a credential: 16 Crockford-base32 symbols in the four
 * dashed groups the account page displays. Deliberately a single repeated
 * character so it carries no entropy for a secret scanner to trip on, while
 * still being exactly as long and as non-numeric as the real thing — which is
 * the property the field has to survive.
 */
const BACKUP_CODE_SHAPE = 'ZZZZ-ZZZZ-ZZZZ-ZZZZ'

/** The 403 the API returns for a second factor it rejected. */
function rejectedSecondFactor() {
  return new AppApiError('Invalid MFA code', 403)
}

/** The 403 the API returns to ask for a second factor in the first place. */
function mfaChallenge() {
  return new AppApiError('MFA code required', 403)
}

const navigate = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => navigate }
})

function setup(entry = '/login') {
  render(
    <MemoryRouter initialEntries={[entry]}>
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

describe('LoginPage backup codes (#77)', () => {
  beforeEach(() => {
    // resetAllMocks, not clearAllMocks: clearing wipes recorded calls but
    // leaves an unconsumed mockResolvedValueOnce queued, so one failing test
    // silently changes the next test's outcome.
    vi.resetAllMocks()
    // Drain the hand-off slot so a count parked by an earlier test cannot be
    // mistaken for one this test produced.
    takeBackupCodesRemaining()
  })

  /** Get to the second-factor step, then switch it to backup-code mode. */
  async function reachBackupCodeField() {
    login.mockRejectedValueOnce(mfaChallenge())
    setup()
    const user = await submitCredentials()
    await screen.findByLabelText(/mfa code/i)
    await user.click(screen.getByRole('button', { name: /use a backup code instead/i }))
    return user
  }

  it('accepts a full 19-character dashed backup code and submits it', async () => {
    const user = await reachBackupCodeField()

    const field = await screen.findByLabelText(/backup code/i)
    await user.type(field, BACKUP_CODE_SHAPE)

    // The bug in #77 was that the field truncated to 6 numeric characters, so
    // asserting the value survived is the actual regression guard.
    expect(field).toHaveValue(BACKUP_CODE_SHAPE)

    login.mockResolvedValueOnce({ id: 'u1' })
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    expect(login).toHaveBeenLastCalledWith(
      expect.objectContaining({ backup_code: BACKUP_CODE_SHAPE, totp_code: undefined }),
    )
    expect(navigate).toHaveBeenCalledWith('/')
  })

  it('does not constrain the backup field to 6 numeric characters', async () => {
    await reachBackupCodeField()
    const field = await screen.findByLabelText(/backup code/i)

    expect(field).not.toHaveAttribute('inputMode', 'numeric')
    expect(Number(field.getAttribute('maxLength'))).toBeGreaterThanOrEqual(
      BACKUP_CODE_SHAPE.length,
    )
  })

  it('shows a rejected backup code exactly as it shows a rejected TOTP code', async () => {
    // The API answers both with the same 403 on purpose, so a caller cannot
    // learn which kind of code they got wrong. The UI must not give that away
    // either, so the two messages are compared directly.
    login.mockRejectedValueOnce(mfaChallenge())
    setup()
    const totpUser = await submitCredentials()
    await totpUser.type(await screen.findByLabelText(/mfa code/i), '000000')
    login.mockRejectedValueOnce(rejectedSecondFactor())
    await totpUser.click(screen.getByRole('button', { name: /sign in/i }))
    const totpMessage = (await screen.findByRole('alert')).textContent

    cleanup()
    vi.clearAllMocks()

    const backupUser = await reachBackupCodeField()
    await backupUser.type(await screen.findByLabelText(/backup code/i), BACKUP_CODE_SHAPE)
    login.mockRejectedValueOnce(rejectedSecondFactor())
    await backupUser.click(screen.getByRole('button', { name: /sign in/i }))
    const backupMessage = (await screen.findByRole('alert')).textContent

    expect(totpMessage).toBeTruthy()
    expect(backupMessage).toBe(totpMessage)
    // And neither may name the kind of code, which would leak the distinction
    // even if the two strings happened to match.
    expect(backupMessage).not.toMatch(/backup|recovery|authenticator/i)
  })

  it('hands the remaining-code count off to the app shell', async () => {
    const user = await reachBackupCodeField()
    await user.type(await screen.findByLabelText(/backup code/i), BACKUP_CODE_SHAPE)

    login.mockResolvedValueOnce({ id: 'u1', backup_codes_remaining: 3 })
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    expect(navigate).toHaveBeenCalledWith('/')
    expect(takeBackupCodesRemaining()).toBe(3)
  })

  it('hands off a remaining count of zero, which is a real value', async () => {
    const user = await reachBackupCodeField()
    await user.type(await screen.findByLabelText(/backup code/i), BACKUP_CODE_SHAPE)

    login.mockResolvedValueOnce({ id: 'u1', backup_codes_remaining: 0 })
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    expect(takeBackupCodesRemaining()).toBe(0)
  })

  it('parks nothing when the sign-in spent no backup code', async () => {
    login.mockResolvedValueOnce({ id: 'u1' })
    setup()
    await submitCredentials()

    expect(takeBackupCodesRemaining()).toBeNull()
  })
})

describe('LoginPage OAuth error codes (#82)', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('tells a refused link to use its password instead of retrying', async () => {
    setup('/login?error=oauth_account_exists')

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/account with this email already exists/i)
    expect(alert).toHaveTextContent(/password/i)
    // The generic fallback tells the user to do the one thing that can never
    // work, which is the whole complaint in #82.
    expect(alert).not.toHaveTextContent(/try again/i)
  })

  it('explains an unverified provider email rather than falling through', async () => {
    setup('/login?error=oauth_email_unverified')

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/not confirmed this email/i)
    expect(alert).not.toHaveTextContent(/^Authentication failed/)
  })

  it('still shows the generic message for a genuinely transient failure', async () => {
    setup('/login?error=oauth_failed')

    expect(await screen.findByRole('alert')).toHaveTextContent(/provider failed/i)
  })

  it('surfaces an unrecognised code in development instead of absorbing it', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    setup('/login?error=some_new_backend_code')

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/some_new_backend_code/)
    expect(warn).toHaveBeenCalledWith(expect.stringContaining('some_new_backend_code'))
    warn.mockRestore()
  })

  it('shows the OAuth error even with no providers configured', async () => {
    // OAuthButtons renders nothing when the provider list is empty, which used
    // to take the error message down with it.
    setup('/login?error=oauth_account_exists')

    expect(screen.queryByRole('button', { name: /continue with/i })).not.toBeInTheDocument()
    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })
})

describe('LoginPage OAuth MFA challenge (#82)', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    takeBackupCodesRemaining()
  })

  it('renders the challenge, and no password prompt, on ?mfa=required', async () => {
    setup('/login?mfa=required')

    expect(await screen.findByLabelText(/mfa code/i)).toBeInTheDocument()
    // The provider leg is already done; asking for a password here would be
    // asking for a factor this flow never had.
    expect(screen.queryByLabelText(/^password$/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument()
  })

  it('completes the challenge with a TOTP code', async () => {
    oauthMfaMutate.mockResolvedValueOnce({ id: 'u1' })
    setup('/login?mfa=required')
    const user = userEvent.setup()

    await user.type(await screen.findByLabelText(/mfa code/i), '123456')
    await user.click(screen.getByRole('button', { name: /verify/i }))

    expect(oauthMfaMutate).toHaveBeenCalledWith({ totp_code: '123456', backup_code: undefined })
    expect(navigate).toHaveBeenCalledWith('/')
  })

  it('completes the challenge with a backup code', async () => {
    oauthMfaMutate.mockResolvedValueOnce({ id: 'u1', backup_codes_remaining: 2 })
    setup('/login?mfa=required')
    const user = userEvent.setup()

    await user.click(screen.getByRole('button', { name: /use a backup code instead/i }))
    const field = await screen.findByLabelText(/backup code/i)
    await user.type(field, BACKUP_CODE_SHAPE)
    expect(field).toHaveValue(BACKUP_CODE_SHAPE)

    await user.click(screen.getByRole('button', { name: /verify/i }))

    expect(oauthMfaMutate).toHaveBeenCalledWith({
      totp_code: undefined,
      backup_code: BACKUP_CODE_SHAPE,
    })
    expect(navigate).toHaveBeenCalledWith('/')
    expect(takeBackupCodesRemaining()).toBe(2)
  })

  it('shows a rejected code without naming which kind it was', async () => {
    oauthMfaMutate.mockRejectedValueOnce(rejectedSecondFactor())
    setup('/login?mfa=required')
    const user = userEvent.setup()

    await user.type(await screen.findByLabelText(/mfa code/i), '000000')
    await user.click(screen.getByRole('button', { name: /verify/i }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/not valid/i)
    expect(alert).not.toHaveTextContent(/backup|recovery|authenticator/i)
    expect(navigate).not.toHaveBeenCalled()
  })

  it('tells the user to start over when the pending token has expired', async () => {
    oauthMfaMutate.mockRejectedValueOnce(new AppApiError('No sign-in awaiting a second factor', 401))
    setup('/login?mfa=required')
    const user = userEvent.setup()

    await user.type(await screen.findByLabelText(/mfa code/i), '123456')
    await user.click(screen.getByRole('button', { name: /verify/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/expired/i)
  })

  it('shows the countdown card when the challenge is throttled', async () => {
    const err = new RateLimitError('Too many requests', 429)
    err.retryAfterSeconds = 60
    oauthMfaMutate.mockRejectedValueOnce(err)
    setup('/login?mfa=required')
    const user = userEvent.setup()

    await user.type(await screen.findByLabelText(/mfa code/i), '123456')
    await user.click(screen.getByRole('button', { name: /verify/i }))

    expect(await screen.findByRole('status')).toHaveTextContent('1:00')
    expect(screen.getByRole('button', { name: /verify/i })).toBeDisabled()
  })
})

describe('LoginPage session-ended notice', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('explains why a password change bounced the user here', () => {
    setup('/login?reason=password_changed')
    expect(screen.getByRole('status')).toHaveTextContent(/password changed/i)
  })

  it('explains why disabling MFA bounced the user here', () => {
    setup('/login?reason=mfa_disabled')
    expect(screen.getByRole('status')).toHaveTextContent(/two-factor/i)
  })

  it('shows nothing for a plain visit or an unknown reason', () => {
    setup('/login?reason=banana')
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})
