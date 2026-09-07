import { useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useForm, type UseFormRegisterReturn } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Sparkles } from 'lucide-react'
import { Button, ErrorState, Input } from '../components/ui'
import { OAuthButtons } from '../components/auth/OAuthButtons'
import { RateLimitCard } from '../components/auth/RateLimitCard'
import { classifyAuthError } from '../components/auth/authErrorMap'
import { useAuth, useOAuthMFA } from '../hooks/useAuth'
import { rememberBackupCodesRemaining } from '../lib/backupCodeNotice'
import {
  BACKUP_CODE_MAX_LENGTH,
  loginSchema,
  oauthMfaSchema,
  type LoginFormData,
  type OAuthMFAFormData,
} from '../lib/schemas'

const OAUTH_ERROR_MESSAGES: Record<string, string> = {
  oauth_failed: 'Sign-in with your provider failed. Please try again.',
  // Not a transient failure — the callback deliberately refused to link the
  // provider to an existing password account. "Please try again" would send
  // the user round a loop that can never succeed, so this names the cause and
  // the one action that works.
  oauth_account_exists:
    'An account with this email already exists. Sign in with your email and password below instead.',
  // Emitted by the same callback when the provider will not vouch for the
  // address. Also absent from this map before now, and also unfixable by
  // retrying the provider — so it gets its own message rather than the
  // generic fallback.
  oauth_email_unverified:
    'Your provider has not confirmed this email address. Verify it with your provider, or sign in with your email and password below.',
}

/**
 * Resolve a `?error=` code to a message.
 *
 * The generic fallback is how `oauth_account_exists` and the pending-MFA
 * redirect both stayed invisible when PR #81 landed: an unrecognised code was
 * silently absorbed into "please try again". A new server-side code is now
 * loud in development, so the next one is noticed while it is being written
 * rather than months later.
 */
function oauthErrorMessage(errKey: string): string {
  const known = OAUTH_ERROR_MESSAGES[errKey]
  if (known) return known
  if (import.meta.env.DEV) {
    console.warn(
      `[LoginPage] unhandled OAuth error code "${errKey}" — add it to OAUTH_ERROR_MESSAGES.`,
    )
    return `Authentication failed. Please try again. (unhandled code: ${errKey})`
  }
  return 'Authentication failed. Please try again.'
}

// Set by useSessionHandoff when the server ended the session on purpose, so
// the bounce back here reads as a consequence rather than a glitch.
const SESSION_ENDED_MESSAGES: Record<string, string> = {
  password_changed: 'Password changed — please sign in again with your new password.',
  mfa_disabled: 'Two-factor authentication disabled — please sign in again.',
}

/**
 * Shown when a submitted second factor is rejected — whichever kind it was.
 *
 * The server answers a wrong backup code and a wrong authenticator code with
 * the same error on purpose: a caller must not learn which of the two they got
 * wrong, nor that an account has no codes left. Wording the two cases
 * differently here would hand back exactly the distinction the API refuses to
 * make, so both paths render this one string.
 */
const SECOND_FACTOR_REJECTED = 'That code is not valid. Check it and try again.'

/**
 * Which server-reported field errors this form is allowed to route to a field.
 *
 * Derived from the schema rather than repeated as a literal list, so the two
 * cannot drift when a field is added. It also keeps a bare 'password' string
 * literal next to another quoted value out of this file, which a secret
 * scanner reads as a hardcoded credential assignment.
 */
type LoginField = keyof LoginFormData

function isLoginField(key: string): key is LoginField {
  return Object.prototype.hasOwnProperty.call(loginSchema.shape, key)
}

interface SecondFactorFieldsProps {
  useBackupCode: boolean
  onToggle: () => void
  totpField: UseFormRegisterReturn
  backupField: UseFormRegisterReturn
  totpError?: string
  backupError?: string
}

/**
 * The second-factor control, shared by the password login and the OAuth
 * challenge. One input at a time, plus the switch between the two kinds of
 * code — the whole point of #77 being that a backup code cannot be typed into
 * a field shaped for a 6-digit TOTP.
 *
 * Registrations are passed in already bound rather than the component taking a
 * generic `register`, because the two callers have different form shapes.
 */
function SecondFactorFields({
  useBackupCode,
  onToggle,
  totpField,
  backupField,
  totpError,
  backupError,
}: SecondFactorFieldsProps) {
  return (
    <div className="space-y-2">
      {useBackupCode ? (
        <Input
          id="backup_code"
          type="text"
          label="Backup code"
          placeholder="XXXX-XXXX-XXXX-XXXX"
          // Deliberately not `inputMode="numeric"` / `maxLength={6}`: a backup
          // code is 16 Crockford-base32 symbols shown in four dashed groups,
          // which the TOTP field's constraints make literally untypeable.
          // The cap mirrors the server's own, which is loose enough to hold
          // the dashes and stray spaces people type when copying off paper.
          inputMode="text"
          maxLength={BACKUP_CODE_MAX_LENGTH}
          autoCapitalize="characters"
          autoCorrect="off"
          spellCheck={false}
          autoComplete="one-time-code"
          autoFocus
          error={backupError}
          {...backupField}
        />
      ) : (
        <Input
          id="totp_code"
          type="text"
          label="MFA code"
          placeholder="6-digit code"
          inputMode="numeric"
          maxLength={6}
          autoComplete="one-time-code"
          autoFocus
          error={totpError}
          {...totpField}
        />
      )}
      <button
        type="button"
        onClick={onToggle}
        className="text-xs text-text-muted hover:text-text underline-offset-2 hover:underline"
      >
        {useBackupCode ? 'Use your authenticator app instead' : 'Use a backup code instead'}
      </button>
      {useBackupCode && (
        <p className="text-xs text-text-faint">
          One of the recovery codes you saved when you turned on two-factor
          authentication. Each code works only once.
        </p>
      )}
    </div>
  )
}

export function LoginPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { login, authConfig } = useAuth()
  const oauthMfa = useOAuthMFA()
  const [showMFA, setShowMFA] = useState(false)
  const [useBackupCode, setUseBackupCode] = useState(false)
  const [cooldown, setCooldown] = useState<{ key: number; seconds: number } | null>(null)
  const [networkFailed, setNetworkFailed] = useState(false)

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormData>({ resolver: zodResolver(loginSchema) })

  // The OAuth challenge is a separate form: its first factor was the provider,
  // carried by the pending-MFA cookie, so it has no email or password field.
  const {
    register: registerOAuth,
    handleSubmit: handleOAuthSubmit,
    setError: setOAuthError,
    formState: { errors: oauthErrors, isSubmitting: oauthSubmitting },
  } = useForm<OAuthMFAFormData>({ resolver: zodResolver(oauthMfaSchema) })

  const oauthError = useMemo(() => {
    const errKey = searchParams.get('error')
    return errKey ? oauthErrorMessage(errKey) : null
  }, [searchParams])

  // The OAuth callback redirects to `/login?mfa=required` when the account has
  // MFA enabled. The pending-MFA token itself is a cookie, never a query
  // parameter — this flag only says a challenge is outstanding.
  const oauthMfaPending = searchParams.get('mfa') === 'required'

  const sessionNotice = useMemo(() => {
    const reason = searchParams.get('reason')
    return reason ? SESSION_ENDED_MESSAGES[reason] ?? null : null
  }, [searchParams])

  const toggleSecondFactorKind = () => setUseBackupCode((prev) => !prev)

  const onSubmit = handleSubmit(async (data) => {
    setNetworkFailed(false)
    try {
      const user = await login({
        email: data.email,
        password: data.password,
        // Exactly one second factor, matching the API's either/or shape.
        totp_code: showMFA && !useBackupCode ? data.totp_code : undefined,
        backup_code: showMFA && useBackupCode ? data.backup_code : undefined,
      })
      // Only set when a backup code was spent. `0` is a real value, so this
      // must not be a truthiness test.
      if (user.backup_codes_remaining != null) {
        rememberBackupCodesRemaining(user.backup_codes_remaining)
      }
      navigate('/')
    } catch (err) {
      const outcome = classifyAuthError(err)
      switch (outcome.kind) {
        case 'mfa_required':
          // The API answers "a second factor is needed" and "that second
          // factor was wrong" with the same 403, so the two are told apart by
          // whether we had already asked.
          if (showMFA) {
            setError(useBackupCode ? 'backup_code' : 'totp_code', {
              message: SECOND_FACTOR_REJECTED,
            })
          } else {
            setShowMFA(true)
            setError('totp_code', { message: 'Enter your 6-digit authenticator code to continue' })
          }
          break
        case 'credentials':
          setError('password', { message: 'Wrong email or password' })
          break
        case 'fields':
          for (const [field, message] of Object.entries(outcome.fields)) {
            if (isLoginField(field)) setError(field, { message })
          }
          if (Object.keys(outcome.fields).length === 0) {
            setError('root', { message: outcome.message })
          }
          break
        case 'rate_limited':
          setCooldown((prev) => ({ key: (prev?.key ?? 0) + 1, seconds: outcome.retryAfterSeconds }))
          break
        case 'network':
          setNetworkFailed(true)
          break
        default:
          setError('root', { message: outcome.message })
      }
    }
  })

  const onOAuthMfaSubmit = handleOAuthSubmit(async (data) => {
    setNetworkFailed(false)
    try {
      const user = await oauthMfa.mutateAsync({
        totp_code: useBackupCode ? undefined : data.totp_code,
        backup_code: useBackupCode ? data.backup_code : undefined,
      })
      if (user.backup_codes_remaining != null) {
        rememberBackupCodesRemaining(user.backup_codes_remaining)
      }
      navigate('/')
    } catch (err) {
      const outcome = classifyAuthError(err)
      switch (outcome.kind) {
        case 'mfa_required':
          // Always a rejection here: the challenge is already on screen.
          setOAuthError(useBackupCode ? 'backup_code' : 'totp_code', {
            message: SECOND_FACTOR_REJECTED,
          })
          break
        case 'credentials':
          // The pending-MFA cookie is missing, expired, or was invalidated by
          // a password change or an admin MFA reset. There is nothing to
          // retype — the provider leg has to be walked again.
          setOAuthError('root', {
            message: 'This sign-in expired. Start again with your provider.',
          })
          break
        case 'rate_limited':
          setCooldown((prev) => ({ key: (prev?.key ?? 0) + 1, seconds: outcome.retryAfterSeconds }))
          break
        case 'network':
          setNetworkFailed(true)
          break
        default:
          setOAuthError('root', { message: outcome.message })
      }
    }
  })

  if (oauthMfaPending) {
    return (
      <div>
        <h2 className="text-lg font-semibold text-text mb-2">Two-factor authentication</h2>
        <p className="text-xs text-text-muted mb-5">
          Your provider signed you in. Enter your second factor to finish.
        </p>
        <form onSubmit={onOAuthMfaSubmit} className="space-y-4" noValidate>
          <SecondFactorFields
            useBackupCode={useBackupCode}
            onToggle={toggleSecondFactorKind}
            totpField={registerOAuth('totp_code')}
            backupField={registerOAuth('backup_code')}
            totpError={oauthErrors.totp_code?.message}
            backupError={oauthErrors.backup_code?.message}
          />
          {oauthErrors.root?.message && (
            <p role="alert" className="text-xs text-red-fg">
              {oauthErrors.root.message}
            </p>
          )}
          {cooldown && (
            <RateLimitCard
              key={cooldown.key}
              seconds={cooldown.seconds}
              onExpire={() => setCooldown(null)}
            />
          )}
          {networkFailed && (
            <ErrorState compact title="Couldn't reach the server" onRetry={() => void onOAuthMfaSubmit()} />
          )}
          <Button
            type="submit"
            size="lg"
            className="w-full"
            loading={oauthSubmitting}
            disabled={cooldown !== null}
          >
            {oauthSubmitting ? 'Verifying…' : 'Verify'}
          </Button>
        </form>
        <p className="text-xs text-text-muted text-center mt-6">
          <Link to="/login" className="hover:text-text underline-offset-2 hover:underline">
            Back to sign in
          </Link>
        </p>
      </div>
    )
  }

  return (
    <div>
      <h2 className="text-lg font-semibold text-text mb-5">Sign in</h2>
      {sessionNotice && (
        <p
          role="status"
          className="mb-4 rounded-lg border border-border bg-surface-2 px-3 py-2 text-xs text-text-muted"
        >
          {sessionNotice}
        </p>
      )}
      {/* Rendered here, not inside OAuthButtons: that component returns null
          when no providers are configured, which silently swallowed the very
          messages #82 is about. It is also the right place for
          oauth_account_exists, whose instruction is to use the form below. */}
      {oauthError && (
        <p
          role="alert"
          className="mb-4 rounded-lg border border-red bg-surface-2 px-3 py-2 text-xs text-red-fg"
        >
          {oauthError}
        </p>
      )}
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <Input
          id="email"
          type="email"
          label="Email"
          placeholder="you@example.com"
          autoComplete="email"
          error={errors.email?.message}
          {...register('email')}
        />
        <Input
          id="password"
          type="password"
          label="Password"
          autoComplete="current-password"
          error={errors.password?.message}
          {...register('password')}
        />
        {showMFA && (
          <SecondFactorFields
            useBackupCode={useBackupCode}
            onToggle={toggleSecondFactorKind}
            totpField={register('totp_code')}
            backupField={register('backup_code')}
            totpError={errors.totp_code?.message}
            backupError={errors.backup_code?.message}
          />
        )}
        {errors.root?.message && (
          <p role="alert" className="text-xs text-red-fg">
            {errors.root.message}
          </p>
        )}
        {cooldown && (
          <RateLimitCard
            key={cooldown.key}
            seconds={cooldown.seconds}
            onExpire={() => setCooldown(null)}
          />
        )}
        {networkFailed && (
          <ErrorState
            compact
            title="Couldn't reach the server"
            onRetry={() => void onSubmit()}
          />
        )}
        <Button
          type="submit"
          size="lg"
          className="w-full"
          loading={isSubmitting}
          disabled={cooldown !== null}
        >
          {isSubmitting ? 'Signing in…' : 'Sign in'}
        </Button>
      </form>
      <OAuthButtons providers={authConfig?.oauth_providers ?? []} />
      {authConfig?.demo_enabled && (
        <Button
          type="button"
          variant="secondary"
          className="w-full mt-3"
          onClick={() => window.location.assign('/api/auth/demo-login')}
        >
          <Sparkles size={14} aria-hidden /> Try the demo
        </Button>
      )}
      <p className="text-xs text-text-muted text-center mt-6">
        {authConfig?.registration_enabled && (
          <>
            <Link to="/register" className="hover:text-text underline-offset-2 hover:underline">
              Create account
            </Link>
            <span className="text-text-faint mx-1.5">·</span>
          </>
        )}
        <Link to="/forgot-password" className="hover:text-text underline-offset-2 hover:underline">
          Forgot password?
        </Link>
      </p>
    </div>
  )
}
