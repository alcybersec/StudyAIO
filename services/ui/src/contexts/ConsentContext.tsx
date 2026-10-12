import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import i18n from '../i18n'
import { authApi } from '../api/auth'
import { setConsentRequiredHandler } from '../api/client'
import { AppApiError } from '../api/errors'
import { ConsentDialog } from '../components/auth/ConsentDialog'
import { useAuth } from '../hooks/useAuth'
import type { AuthUser } from '../types'

/**
 * Owns the AI-consent disclosure.
 *
 * Two things open it: the profile saying `ai_consent_required`, and any API
 * response of 403 `ai_consent_required` (the API client calls the handler
 * registered here, waits for the answer, and retries the request once on
 * agreement). Declining closes it and leaves AI features refusing; nothing else
 * in the app depends on consent.
 */
export function ConsentProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const queryClient = useQueryClient()

  const [open, setOpen] = useState(false)
  const [version, setVersion] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [changed, setChanged] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const waiters = useRef<((accepted: boolean) => void)[]>([])
  // The user the profile prompt was declined for, so "Not now" is not nagged
  // again until a different account signs in.
  const declinedFor = useRef<string | null>(null)

  const userId = user?.id ?? null
  const required = !!user?.ai_consent_required
  const profileVersion = user?.ai_consent_version ?? null

  useEffect(() => {
    if (required && declinedFor.current !== userId) {
      setOpen(true)
      setVersion((v) => v ?? profileVersion)
    }
  }, [required, userId, profileVersion])

  useEffect(() => {
    setConsentRequiredHandler(
      (consentVersion) =>
        new Promise<boolean>((resolve) => {
          waiters.current.push(resolve)
          setVersion((v) => consentVersion ?? v)
          setOpen(true)
        }),
    )
    return () => setConsentRequiredHandler(null)
  }, [])

  const settle = useCallback((accepted: boolean) => {
    setOpen(false)
    setChanged(false)
    setError(null)
    const pending = waiters.current
    waiters.current = []
    for (const resolve of pending) resolve(accepted)
  }, [])

  const decline = useCallback(() => {
    declinedFor.current = userId
    settle(false)
  }, [settle, userId])

  const accept = useCallback(async () => {
    setBusy(true)
    setError(null)
    try {
      await authApi.consent(version)
      queryClient.setQueryData<AuthUser | null | undefined>(['auth', 'me'], (u) =>
        u ? { ...u, ai_consent_required: false } : u,
      )
      settle(true)
    } catch (err) {
      if (err instanceof AppApiError && err.status === 409) {
        // The wording moved on while this page was open: reload what the
        // server now requires and show the disclosure again.
        const fresh = await authApi.me().catch(() => null)
        if (fresh) queryClient.setQueryData(['auth', 'me'], fresh)
        setVersion(fresh?.ai_consent_version ?? null)
        setChanged(true)
      } else {
        setError(i18n.t("Couldn't save your choice. Please try again."))
      }
    } finally {
      setBusy(false)
    }
  }, [version, queryClient, settle])

  return (
    <>
      {children}
      <ConsentDialog
        open={open}
        busy={busy}
        changed={changed}
        error={error}
        onAccept={() => void accept()}
        onDecline={decline}
      />
    </>
  )
}
