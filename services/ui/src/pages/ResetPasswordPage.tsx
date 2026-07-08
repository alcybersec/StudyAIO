import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { KeyRound } from 'lucide-react'
import { Button, ErrorState, Input } from '../components/ui'
import { RateLimitCard } from '../components/auth/RateLimitCard'
import { classifyAuthError } from '../components/auth/authErrorMap'
import { authApi } from '../api/auth'
import { resetPasswordSchema, type ResetPasswordFormData } from '../lib/schemas'

const RESET_FIELDS = ['password', 'confirm'] as const
type ResetField = (typeof RESET_FIELDS)[number]

function isResetField(key: string): key is ResetField {
  return (RESET_FIELDS as readonly string[]).includes(key)
}

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') ?? ''
  const [success, setSuccess] = useState(false)
  const [cooldown, setCooldown] = useState<{ key: number; seconds: number } | null>(null)
  const [networkFailed, setNetworkFailed] = useState(false)

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ResetPasswordFormData>({ resolver: zodResolver(resetPasswordSchema) })

  const onSubmit = handleSubmit(async (data) => {
    setNetworkFailed(false)
    if (!token) {
      setError('root', { message: 'This reset link is invalid or has expired' })
      return
    }
    try {
      await authApi.resetPassword({ token, new_password: data.password })
      setSuccess(true)
    } catch (err) {
      const outcome = classifyAuthError(err)
      switch (outcome.kind) {
        case 'fields': {
          let mapped = false
          for (const [field, message] of Object.entries(outcome.fields)) {
            const key = field === 'new_password' ? 'password' : field
            if (isResetField(key)) {
              setError(key, { message })
              mapped = true
            }
          }
          if (!mapped) setError('root', { message: outcome.message })
          break
        }
        case 'credentials':
          setError('root', { message: 'This reset link is invalid or has expired' })
          break
        case 'rate_limited':
          setCooldown((prev) => ({ key: (prev?.key ?? 0) + 1, seconds: outcome.retryAfterSeconds }))
          break
        case 'network':
          setNetworkFailed(true)
          break
        default:
          setError('root', {
            message: 'message' in outcome ? outcome.message : 'Reset failed',
          })
      }
    }
  })

  if (success) {
    return (
      <div className="text-center space-y-4">
        <span className="mx-auto w-10 h-10 rounded-xl bg-sage-soft text-sage-fg flex items-center justify-center">
          <KeyRound size={18} aria-hidden />
        </span>
        <h2 className="text-lg font-semibold text-text">Password reset!</h2>
        <p className="text-sm text-text-muted">Your password has been updated.</p>
        <Link
          to="/login"
          className="inline-flex items-center justify-center min-h-[44px] px-6 bg-sage text-on-accent rounded-lg text-sm font-semibold hover:bg-sage-hover transition-colors"
        >
          Sign in
        </Link>
      </div>
    )
  }

  return (
    <div>
      <h2 className="text-lg font-semibold text-text mb-5">Set new password</h2>
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <Input
          id="password"
          type="password"
          label="New password"
          placeholder="At least 8 characters"
          autoComplete="new-password"
          error={errors.password?.message}
          {...register('password')}
        />
        <Input
          id="confirm"
          type="password"
          label="Confirm new password"
          autoComplete="new-password"
          error={errors.confirm?.message}
          {...register('confirm')}
        />
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
          {isSubmitting ? 'Resetting…' : 'Reset password'}
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
