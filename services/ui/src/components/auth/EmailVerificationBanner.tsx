import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { authApi } from '../../api/auth'
import { RateLimitError } from '../../api/errors'
import { useAuth } from '../../hooks/useAuth'

/**
 * Slim notice for logged-in, password-registered users whose email is not yet
 * verified. Purely informational — nothing in the app gates on the flag — but
 * it lets the user complete verification without waiting for the next email.
 * Renders nothing for verified, demo, or anonymous sessions.
 */
export function EmailVerificationBanner() {
  const { user, isDemo } = useAuth()
  const [dismissed, setDismissed] = useState(false)
  const [resent, setResent] = useState(false)
  const [rateLimited, setRateLimited] = useState(false)

  const resend = useMutation({
    mutationFn: authApi.resendVerification,
    onSuccess: () => {
      setResent(true)
      setRateLimited(false)
    },
    onError: (err) => {
      setRateLimited(err instanceof RateLimitError)
    },
  })

  if (!user || user.email_verified || isDemo || dismissed) return null

  return (
    <div className="bg-amber text-on-accent text-center text-sm py-2 px-4 flex items-center justify-center gap-3 sticky top-0 z-50">
      {resent ? (
        <span role="status">Verification email sent — check your inbox.</span>
      ) : (
        <>
          <span>Your email isn't verified yet.</span>
          <button
            type="button"
            onClick={() => resend.mutate()}
            disabled={resend.isPending || rateLimited}
            className="inline-flex items-center px-3 py-1 rounded-md bg-on-accent text-amber text-xs font-semibold hover:opacity-90 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {resend.isPending ? 'Sending…' : 'Resend verification email'}
          </button>
          {rateLimited && (
            <span role="alert" className="text-xs">
              Too many attempts — try again in a minute.
            </span>
          )}
        </>
      )}
      <button
        type="button"
        aria-label="Dismiss verification notice"
        onClick={() => setDismissed(true)}
        className="inline-flex items-center justify-center w-8 h-8 rounded-md hover:bg-on-accent/10 transition-colors"
      >
        <X size={14} aria-hidden />
      </button>
    </div>
  )
}
