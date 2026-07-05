import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Button, ErrorState, Input } from '../components/ui'
import { RateLimitCard } from '../components/auth/RateLimitCard'
import { classifyAuthError } from '../components/auth/authErrorMap'
import { useAuth } from '../hooks/useAuth'
import { registerSchema, type RegisterFormData } from '../lib/schemas'

const REGISTER_FIELDS = ['email', 'username', 'password', 'confirm'] as const
type RegisterField = (typeof REGISTER_FIELDS)[number]

function isRegisterField(key: string): key is RegisterField {
  return (REGISTER_FIELDS as readonly string[]).includes(key)
}

export function RegisterPage() {
  const navigate = useNavigate()
  const { register: registerUser } = useAuth()
  const [cooldown, setCooldown] = useState<{ key: number; seconds: number } | null>(null)
  const [networkFailed, setNetworkFailed] = useState(false)

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormData>({ resolver: zodResolver(registerSchema) })

  const onSubmit = handleSubmit(async (data) => {
    setNetworkFailed(false)
    try {
      await registerUser({ email: data.email, username: data.username, password: data.password })
      navigate('/')
    } catch (err) {
      const outcome = classifyAuthError(err)
      switch (outcome.kind) {
        case 'fields':
          for (const [field, message] of Object.entries(outcome.fields)) {
            if (isRegisterField(field)) setError(field, { message })
          }
          if (Object.keys(outcome.fields).length === 0) {
            setError('root', { message: outcome.message })
          }
          break
        case 'conflict':
          setError('email', { message: 'An account with this email already exists' })
          break
        case 'rate_limited':
          setCooldown((prev) => ({ key: (prev?.key ?? 0) + 1, seconds: outcome.retryAfterSeconds }))
          break
        case 'network':
          setNetworkFailed(true)
          break
        default:
          setError('root', {
            message: 'message' in outcome ? outcome.message : 'Registration failed',
          })
      }
    }
  })

  return (
    <div>
      <h2 className="text-lg font-semibold text-text mb-5">Create account</h2>
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
          id="username"
          type="text"
          label="Username"
          placeholder="johndoe"
          autoComplete="username"
          error={errors.username?.message}
          {...register('username')}
        />
        <Input
          id="password"
          type="password"
          label="Password"
          placeholder="At least 8 characters"
          autoComplete="new-password"
          error={errors.password?.message}
          {...register('password')}
        />
        <Input
          id="confirm"
          type="password"
          label="Confirm password"
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
          {isSubmitting ? 'Creating account…' : 'Create account'}
        </Button>
      </form>
      <p className="text-xs text-text-muted text-center mt-6">
        Already have an account?{' '}
        <Link to="/login" className="hover:text-text underline-offset-2 hover:underline">
          Sign in
        </Link>
      </p>
    </div>
  )
}
