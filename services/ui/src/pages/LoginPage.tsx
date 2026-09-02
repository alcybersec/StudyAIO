import { useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Sparkles } from 'lucide-react'
import { Button, ErrorState, Input } from '../components/ui'
import { OAuthButtons } from '../components/auth/OAuthButtons'
import { RateLimitCard } from '../components/auth/RateLimitCard'
import { classifyAuthError } from '../components/auth/authErrorMap'
import { useAuth } from '../hooks/useAuth'
import { loginSchema, type LoginFormData } from '../lib/schemas'

const OAUTH_ERROR_MESSAGES: Record<string, string> = {
  oauth_failed: 'Sign-in with your provider failed. Please try again.',
}

// Set by useSessionHandoff when the server ended the session on purpose, so
// the bounce back here reads as a consequence rather than a glitch.
const SESSION_ENDED_MESSAGES: Record<string, string> = {
  password_changed: 'Password changed — please sign in again with your new password.',
  mfa_disabled: 'Two-factor authentication disabled — please sign in again.',
}

const LOGIN_FIELDS = ['email', 'password', 'totp_code'] as const
type LoginField = (typeof LOGIN_FIELDS)[number]

function isLoginField(key: string): key is LoginField {
  return (LOGIN_FIELDS as readonly string[]).includes(key)
}

export function LoginPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { login, authConfig } = useAuth()
  const [showMFA, setShowMFA] = useState(false)
  const [cooldown, setCooldown] = useState<{ key: number; seconds: number } | null>(null)
  const [networkFailed, setNetworkFailed] = useState(false)

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormData>({ resolver: zodResolver(loginSchema) })

  const oauthError = useMemo(() => {
    const errKey = searchParams.get('error')
    return errKey
      ? OAUTH_ERROR_MESSAGES[errKey] ?? 'Authentication failed. Please try again.'
      : null
  }, [searchParams])

  const sessionNotice = useMemo(() => {
    const reason = searchParams.get('reason')
    return reason ? SESSION_ENDED_MESSAGES[reason] ?? null : null
  }, [searchParams])

  const onSubmit = handleSubmit(async (data) => {
    setNetworkFailed(false)
    try {
      await login({
        email: data.email,
        password: data.password,
        totp_code: showMFA ? data.totp_code : undefined,
      })
      navigate('/')
    } catch (err) {
      const outcome = classifyAuthError(err)
      switch (outcome.kind) {
        case 'mfa_required':
          setShowMFA(true)
          setError('totp_code', { message: 'Enter your 6-digit authenticator code to continue' })
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
          <Input
            id="totp_code"
            type="text"
            label="MFA code"
            placeholder="6-digit code"
            inputMode="numeric"
            maxLength={6}
            autoComplete="one-time-code"
            autoFocus
            error={errors.totp_code?.message}
            {...register('totp_code')}
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
      <OAuthButtons providers={authConfig?.oauth_providers ?? []} error={oauthError} />
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
