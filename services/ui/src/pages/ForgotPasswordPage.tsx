import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { MailCheck } from 'lucide-react'
import { Button, ErrorState, Input } from '../components/ui'
import { RateLimitCard } from '../components/auth/RateLimitCard'
import { classifyAuthError } from '../components/auth/authErrorMap'
import { authApi } from '../api/auth'
import { forgotPasswordSchema, type ForgotPasswordFormData } from '../lib/schemas'

export function ForgotPasswordPage() {
  const [submitted, setSubmitted] = useState(false)
  const [cooldown, setCooldown] = useState<{ key: number; seconds: number } | null>(null)
  const [networkFailed, setNetworkFailed] = useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ForgotPasswordFormData>({ resolver: zodResolver(forgotPasswordSchema) })

  const onSubmit = handleSubmit(async (data) => {
    setNetworkFailed(false)
    try {
      await authApi.forgotPassword({ email: data.email })
      setSubmitted(true)
    } catch (err) {
      const outcome = classifyAuthError(err)
      if (outcome.kind === 'rate_limited') {
        setCooldown((prev) => ({ key: (prev?.key ?? 0) + 1, seconds: outcome.retryAfterSeconds }))
      } else if (outcome.kind === 'network') {
        setNetworkFailed(true)
      } else {
        // Enumeration-safe: any other failure looks identical to success.
        setSubmitted(true)
      }
    }
  })

  if (submitted) {
    return (
      <div className="text-center space-y-4">
        <span className="mx-auto w-10 h-10 rounded-xl bg-sage-soft text-sage-fg flex items-center justify-center">
          <MailCheck size={18} aria-hidden />
        </span>
        <h2 className="text-lg font-semibold text-text">Check your email</h2>
        <p className="text-sm text-text-muted">
          If an account exists with that email, we&apos;ve sent a password reset link.
        </p>
        <Link
          to="/login"
          className="inline-block text-xs text-text-muted hover:text-text underline-offset-2 hover:underline"
        >
          Back to sign in
        </Link>
      </div>
    )
  }

  return (
    <div>
      <h2 className="text-lg font-semibold text-text mb-1.5">Reset password</h2>
      <p className="text-xs text-text-muted mb-5">
        Enter your email and we&apos;ll send you a reset link.
      </p>
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
          {isSubmitting ? 'Sending…' : 'Send reset link'}
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
