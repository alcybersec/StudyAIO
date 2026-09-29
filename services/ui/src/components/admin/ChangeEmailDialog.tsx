import { useState } from 'react'
import i18n from '../../i18n'
import { useTranslation } from 'react-i18next'
import { TriangleAlert } from 'lucide-react'
import { toast } from 'sonner'
import { Button, Input, Modal } from '../ui'
import { useAdminUserDetail, useResendVerification, useUpdateAdminUser } from '../../hooks/useApi'
import { adminEmailSchema, normalizeEmail } from '../../lib/schemas'
import type { AdminUser } from '../../types'

interface ChangeEmailDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  user: AdminUser
}

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof Error && err.message ? err.message : fallback
}

/** Display names for the providers the backend records, which are lowercase. */
const PROVIDER_LABELS: Record<string, string> = {
  google: 'Google',
  github: 'GitHub',
}

function providerLabel(provider: string): string {
  return PROVIDER_LABELS[provider] ?? provider
}

/** "Google", "Google and GitHub", "Google, GitHub and X". */
function listProviders(providers: string[]): string {
  const names = providers.map(providerLabel)
  if (names.length <= 1) return names[0] ?? ''
  return `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`
}

/**
 * Repoint a user's login address.
 *
 * A modal, and not a field in the users table, because every other control in
 * that table commits on change. A free-text email input in a row like that
 * would sit one stray keystroke and one blur away from unlinking someone's
 * Google account. Text that ends sessions needs an explicit submit and a screen
 * with room for the consequences.
 *
 * There is deliberately no gentler "just fixing a typo" variant. The server
 * unlinks OAuth unconditionally (#88 rejected an opt-out), so a second door
 * labelled harmless would have to lie about what it does — and an operator
 * offered two doors to one destructive operation learns to take the calm one.
 * One door, accurately labelled.
 */
export function ChangeEmailDialog({ open, onOpenChange, user }: ChangeEmailDialogProps) {
  const { t } = useTranslation()

  const [email, setEmail] = useState('')
  const [confirmEmail, setConfirmEmail] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [changedTo, setChangedTo] = useState<string | null>(null)

  const updateUser = useUpdateAdminUser()
  const resendVerification = useResendVerification()

  const reset = () => {
    setEmail('')
    setConfirmEmail('')
    setError(null)
    setChangedTo(null)
  }

  const close = () => {
    reset()
    onOpenChange(false)
  }

  // Only while the dialog is open: the list row cannot carry this, and the
  // warning below is the only thing that needs it. `undefined` disables the
  // query (see `useAdminUserDetail`).
  const details = useAdminUserDetail(open ? user.id : undefined)
  const linkedProviders = details.data?.profile.oauth_providers ?? null

  const normalized = normalizeEmail(email)
  const parsed = adminEmailSchema.safeParse(email.trim())
  // Checked against the normalized stored address, because that is what the
  // server compares: since #91 a case- or whitespace-only difference is a
  // genuine no-op there, so offering to "change" it would promise a sign-out
  // and an OAuth unlink that will not happen.
  const isSameAddress = parsed.success && normalized === normalizeEmail(user.email)
  const confirmMatches = normalized === normalizeEmail(confirmEmail)
  const canSubmit = parsed.success && !isSameAddress && confirmMatches && !updateUser.isPending

  const submit = () => {
    setError(null)
    updateUser.mutate(
      { userId: user.id, data: { email: normalized } },
      {
        onSuccess: () => setChangedTo(normalized),
        onError: (err) =>
          setError(
            errorMessage(err, "Couldn't change the address — nothing was changed on the account"),
          ),
      },
    )
  }

  if (changedTo) {
    return (
      <Modal
        open={open}
        onOpenChange={(next) => (next ? onOpenChange(true) : close())}
        title={t('Email changed')}
      >
        <div className="space-y-3">
          <p className="text-xs text-text-muted">
            {t('This account now signs in as')} <span className="font-medium text-text">{changedTo}</span>{t('. It is unverified, and the user is signed out everywhere with their sign-in providers unlinked.')}
          </p>
          <p className="text-xs text-text-muted">
            {t('Send them a verification link now — they have not been told any of this, and nothing was sent to the old address.')}
          </p>
          <div className="flex gap-2 pt-1">
            <Button
              size="sm"
              disabled={resendVerification.isPending}
              onClick={() =>
                resendVerification.mutate(user.id, {
                  onSuccess: (r) => {
                    if (r.email_sent) {
                      toast.success(`Verification link sent to ${changedTo}`)
                      return
                    }
                    void navigator.clipboard
                      .writeText(r.url)
                      .then(() => toast.success(i18n.t(i18n.t('No email configured — link copied to clipboard'))))
                      .catch(() => toast.message(i18n.t(i18n.t('No email configured. Link:')), { description: r.url }))
                  },
                  onError: (e) =>
                    toast.error(errorMessage(e, i18n.t("Couldn't create a verification link"))),
                })
              }
            >
              {resendVerification.isPending ? 'Sending…' : 'Send verification link'}
            </Button>
            <Button variant="ghost" size="sm" onClick={close}>
              {t('Done')}
            </Button>
          </div>
        </div>
      </Modal>
    )
  }

  return (
    <Modal
      open={open}
      onOpenChange={(next) => (next ? onOpenChange(true) : close())}
      title={`Change the email for ${user.email}?`}
    >
      <div className="space-y-3">
        <p className="flex items-start gap-2 text-xs text-red-fg">
          <TriangleAlert size={14} className="mt-px shrink-0" aria-hidden />
          <span>
            {t('This is a remediation, not a correction. It cuts every standing route back into the account:')}
          </span>
        </p>

        <ul className="space-y-1.5 text-xs text-text-muted list-disc pl-4">
          <li>
            {t('Signs {{email}} out on every device immediately — the access token and the 7-day refresh token both stop working, so they cannot silently resume.', { email: user.email })}
          </li>
          {/*
            Three states, and they are not interchangeable (GL#3). A known list
            names what breaks; an empty list means nothing is linked, so the
            warning is dropped rather than shown about a user it cannot apply
            to; and `null` — the lookup failed, or is still in flight — falls
            back to the generic wording, because the one thing we must not do is
            state that a destructive action breaks no links when we do not know.
          */}
          {linkedProviders === null ? (
            <li>
              <span className="font-medium text-text">
                {t('Unlinks every connected sign-in provider')}
              </span>{' '}
              {t('(Google, GitHub). All of them: the links are not recorded against an address, so there is no way to unlink only the one tied to the old inbox.')}
            </li>
          ) : linkedProviders.length > 0 ? (
            <li>
              <span className="font-medium text-text">
                {t('Unlinks their {{providers}} sign-in', { providers: listProviders(linkedProviders) })}
              </span>
              {linkedProviders.length > 1 ? t(' — both of them') : ''}
              {t('. The links are not recorded against an address, so there is no way to unlink only the one tied to the old inbox.')}
            </li>
          ) : null}
          <li>
            <span className="font-medium text-text">
              {t('If this account has a password, re-linking is not automatic.')}
            </span>{' '}
            {t('Signing in with the provider again will be refused; they have to use their password. This is the one part your cleanup cannot fix for them.')}
          </li>
          <li>
            {t('Voids every unused link already sent to the old address — including a pending set-password link. An account that was created but never claimed then has no way in until you issue a new one.')}
          </li>
          <li>
            {t('Marks the new address unverified. Send a verification link straight after; this dialog offers one.')}
          </li>
          <li>
            {t('Mail goes only to the new address from now on. The old inbox is told nothing, so if the address was simply wrong rather than compromised, tell the user some other way.')}
          </li>
          <li>
            {t('If the new address already belongs to another account, the change is refused outright — nothing is merged and nothing is half-applied.')}
          </li>
        </ul>

        <Input
          id={`change-email-${user.id}`}
          type="email"
          label={t('New email address')}
          autoComplete="off"
          placeholder="tester@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={
            email.trim() && !parsed.success
              ? parsed.error.issues[0]?.message
              : isSameAddress
                ? 'That is already this account’s address — capitalisation and spacing are ignored, so this would change nothing.'
                : undefined
          }
        />

        <Input
          id={`change-email-confirm-${user.id}`}
          type="email"
          label={t('Type the new address again')}
          autoComplete="off"
          value={confirmEmail}
          onChange={(e) => setConfirmEmail(e.target.value)}
          error={confirmEmail && !confirmMatches ? 'The two addresses do not match' : undefined}
        />

        {error && (
          <p role="alert" className="text-xs text-red-fg">
            {error}
          </p>
        )}

        <div className="flex gap-2 pt-1">
          <Button variant="danger" size="sm" disabled={!canSubmit} onClick={submit}>
            {updateUser.isPending ? 'Changing…' : 'Change email and sign them out'}
          </Button>
          <Button variant="ghost" size="sm" disabled={updateUser.isPending} onClick={close}>
            {t('Cancel')}
          </Button>
        </div>
      </div>
    </Modal>
  )
}
