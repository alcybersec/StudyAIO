import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Button, ErrorState, Input } from '../components/ui'
import { RateLimitCard } from '../components/auth/RateLimitCard'
import { classifyAuthError } from '../components/auth/authErrorMap'
import { useAuth } from '../hooks/useAuth'
import { registerSchema, type RegisterFormData } from '../lib/schemas'

const REGISTER_FIELDS = ['email', 'username', 'password', 'confirm', 'invite_code'] as const
type RegisterField = (typeof REGISTER_FIELDS)[number]

function isRegisterField(key: string): key is RegisterField {
  return (REGISTER_FIELDS as readonly string[]).includes(key)
}

export function RegisterPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { register: registerUser, authConfig } = useAuth()
  const inviteRequired = authConfig?.invite_required ?? false
  // An emailed invite arrives as /register?invite=<token>. The token goes into
  // the same field a typed code does, so the server has one redemption path.
  const [searchParams] = useSearchParams()
  const inviteFromLink = searchParams.get('invite')?.trim() ?? ''
  const [cooldown, setCooldown] = useState<{ key: number; seconds: number } | null>(null)
  const [networkFailed, setNetworkFailed] = useState(false)

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
    defaultValues: { invite_code: inviteFromLink },
  })

  const onSubmit = handleSubmit(async (data) => {
    setNetworkFailed(false)
    if (inviteRequired && !data.invite_code?.trim()) {
      setError('invite_code', { message: t('An invite code is required') })
      return
    }
    try {
      await registerUser({
        email: data.email,
        username: data.username,
        password: data.password,
        ...(inviteRequired ? { invite_code: data.invite_code?.trim() } : {}),
      })
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
          setError('email', { message: t('An account with this email already exists') })
          break
        case 'rate_limited':
          setCooldown((prev) => ({ key: (prev?.key ?? 0) + 1, seconds: outcome.retryAfterSeconds }))
          break
        case 'network':
          setNetworkFailed(true)
          break
        default:
          setError('root', {
            message: 'message' in outcome ? outcome.message : t('Registration failed'),
          })
      }
    }
  })

  return (
    <div>
      <h2 className="text-lg font-semibold text-text mb-5">{t('Create account')}</h2>
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <Input
          id="email"
          type="email"
          label={t('Email')}
          placeholder="you@example.com"
          autoComplete="email"
          error={errors.email?.message}
          {...register('email')}
        />
        <Input
          id="username"
          type="text"
          label={t('Username')}
          placeholder={t('johndoe')}
          autoComplete="username"
          error={errors.username?.message}
          {...register('username')}
        />
        <Input
          id="password"
          type="password"
          label={t('Password')}
          placeholder={t('At least 8 characters')}
          autoComplete="new-password"
          error={errors.password?.message}
          {...register('password')}
        />
        <Input
          id="confirm"
          type="password"
          label={t('Confirm password')}
          autoComplete="new-password"
          error={errors.confirm?.message}
          {...register('confirm')}
        />
        {inviteRequired &&
          (inviteFromLink ? (
            // Registered but not rendered as a text input on purpose. The code
            // field carries autoCapitalize="characters", which is right for a
            // hand-typed BETA- code and would destroy a base64url token if the
            // recipient so much as focused it.
            <>
              <input type="hidden" {...register('invite_code')} />
              <p className="text-xs text-text-muted">
                {t('You’re signing up with an invite link.')}
              </p>
              {errors.invite_code?.message && (
                <p role="alert" className="text-xs text-red-fg">
                  {errors.invite_code.message}
                </p>
              )}
            </>
          ) : (
            <Input
              id="invite_code"
              type="text"
              label={t('Invite code')}
              placeholder="BETA-XXXXXXXX"
              autoComplete="off"
              autoCapitalize="characters"
              spellCheck={false}
              error={errors.invite_code?.message}
              {...register('invite_code')}
            />
          ))}
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
            title={t("Couldn't reach the server")}
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
          {isSubmitting ? t('Creating account…') : t('Create account')}
        </Button>
      </form>
      <p className="text-xs text-text-muted text-center mt-6">
        {t('Already have an account?')}{' '}
        <Link to="/login" className="hover:text-text underline-offset-2 hover:underline">
          {t('Sign in')}
        </Link>
      </p>
    </div>
  )
}
