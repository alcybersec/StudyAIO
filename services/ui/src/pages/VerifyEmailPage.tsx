import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { MailCheck, MailX } from 'lucide-react'
import { Button, ErrorState, LoadingSpinner } from '../components/ui'
import { NetworkError } from '../api/errors'
import { authApi } from '../api/auth'
import { useAuth } from '../hooks/useAuth'

/**
 * Email verification landing page. The verification email links here with a
 * ?token= query param; the token is posted once on mount and the result is
 * reported. Reachable whether or not the user has a session — the link is
 * often clicked from a mail client while already logged in.
 */
export function VerifyEmailPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') ?? ''
  const { user } = useAuth()
  const queryClient = useQueryClient()
  // The POST fires exactly once per token: StrictMode double-invokes effects
  // in dev, and a second POST against a single-use token would flip a success
  // into "already used".
  const started = useRef(false)
  const [resent, setResent] = useState(false)

  const verify = useMutation({
    mutationFn: (t: string) => authApi.verifyEmail({ token: t }),
    onSuccess: () => {
      // Refresh the session so an unverified-notice banner clears immediately.
      void queryClient.invalidateQueries({ queryKey: ['auth', 'me'] })
    },
  })

  const resend = useMutation({
    mutationFn: authApi.resendVerification,
    onSuccess: () => setResent(true),
  })

  useEffect(() => {
    if (started.current || !token) return
    started.current = true
    verify.mutate(token)
    // Fires once per token value; `verify.mutate` is stable for this purpose.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  if (verify.isPending) {
    return (
      <div className="text-center space-y-4 py-6" role="status">
        <LoadingSpinner size="lg" label="Verifying your email..." />
        <p className="text-sm text-text-muted">Checking your verification link…</p>
      </div>
    )
  }

  if (verify.isSuccess) {
    return (
      <div className="text-center space-y-4">
        <span className="mx-auto w-10 h-10 rounded-xl bg-sage-soft text-sage-fg flex items-center justify-center">
          <MailCheck size={18} aria-hidden />
        </span>
        <h2 className="text-lg font-semibold text-text">Email verified!</h2>
        <p className="text-sm text-text-muted">Thanks — your email address is confirmed.</p>
        <Link
          to="/"
          className="inline-flex items-center justify-center min-h-[44px] px-6 bg-sage text-on-accent rounded-lg text-sm font-semibold hover:bg-sage-hover transition-colors"
        >
          Go to dashboard
        </Link>
      </div>
    )
  }

  // Failure: no token in the URL, or the API rejected it (invalid/expired/used).
  const networkFailed = verify.isError && verify.error instanceof NetworkError
  return (
    <div className="text-center space-y-4">
      <span className="mx-auto w-10 h-10 rounded-xl bg-red-soft text-red-fg flex items-center justify-center">
        <MailX size={18} aria-hidden />
      </span>
      <h2 className="text-lg font-semibold text-text">Couldn't verify your email</h2>
      <p className="text-sm text-text-muted" role="alert">
        This verification link is invalid or has expired.
      </p>
      {networkFailed && (
        <ErrorState
          compact
          title="Couldn't reach the server"
          onRetry={() => verify.mutate(token)}
        />
      )}
      {user && !user.email_verified && !resent && (
        <Button
          onClick={() => resend.mutate()}
          loading={resend.isPending}
          className="min-h-[44px]"
        >
          {resend.isPending ? 'Sending…' : 'Resend verification email'}
        </Button>
      )}
      {resent && (
        <p className="text-sm text-text-muted" role="status">
          Verification email sent — check your inbox.
        </p>
      )}
      <p className="text-xs text-text-muted">
        <Link to="/login" className="hover:text-text underline-offset-2 hover:underline">
          Back to sign in
        </Link>
      </p>
    </div>
  )
}
