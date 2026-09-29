import { useState } from 'react'
import i18n from '../../i18n'
import { useTranslation } from 'react-i18next'
import { AtSign, KeyRound, MailCheck, ShieldOff, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '../ui'
import {
  useClearUserMfa,
  useDeleteAdminUser,
  useResendVerification,
  useSendPasswordReset,
} from '../../hooks/useApi'
import type { AdminUser } from '../../types'
import { ChangeEmailDialog } from './ChangeEmailDialog'
import { ConfirmAction } from './ConfirmAction'

interface UserRowActionsProps {
  user: AdminUser
  /** The signed-in admin, who cannot delete themselves from here. */
  currentUserId: string | undefined
}

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof Error && err.message ? err.message : fallback
}

/**
 * Per-user admin actions: password reset, resend verification, change email,
 * clear MFA, delete.
 *
 * Three of these are destructive and they do not all get the same friction,
 * because they do not all carry the same risk of being misread:
 *
 * - Deletion is irreversible, and the word already says so: a second click.
 * - Clearing MFA and changing the email both end the user's sessions and read
 *   like housekeeping, so they state their consequences in a modal first.
 * - Changing the email additionally asks for the address twice — this table is
 *   paginated and its rows are one click apart.
 */
export function UserRowActions({ user, currentUserId }: UserRowActionsProps) {
  const { t } = useTranslation()

  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const [changingEmail, setChangingEmail] = useState(false)
  const [confirmingMfaReset, setConfirmingMfaReset] = useState(false)

  const sendReset = useSendPasswordReset()
  const resendVerification = useResendVerification()
  const clearMfa = useClearUserMfa()
  const deleteUser = useDeleteAdminUser()

  const isSelf = user.id === currentUserId

  const showLink = (url: string, emailSent: boolean, sentMsg: string) => {
    if (emailSent) {
      toast.success(sentMsg)
      return
    }
    // No SMTP — the admin has to relay it, so put it on the clipboard.
    void navigator.clipboard
      .writeText(url)
      .then(() => toast.success(i18n.t('No email configured — link copied to clipboard')))
      .catch(() => toast.message(i18n.t('No email configured. Link:'), { description: url }))
  }

  return (
    <div className="flex items-center justify-end gap-1" onClick={(e) => e.stopPropagation()}>
      <Button
        variant="ghost"
        size="sm"
        disabled={sendReset.isPending}
        title={t('Send a password reset link')}
        onClick={() =>
          sendReset.mutate(user.id, {
            onSuccess: (r) => showLink(r.url, r.email_sent, 'Password reset emailed'),
            onError: (e) => toast.error(errorMessage(e, i18n.t("Couldn't create a reset link"))),
          })
        }
      >
        <KeyRound size={12} aria-hidden />
        <span className="sr-only">{t('Send password reset to {{email}}', { email: user.email })}</span>
      </Button>

      <Button
        variant="ghost"
        size="sm"
        disabled={resendVerification.isPending}
        title={t('Resend the verification email')}
        onClick={() =>
          resendVerification.mutate(user.id, {
            onSuccess: (r) => showLink(r.url, r.email_sent, 'Verification email sent'),
            onError: (e) => toast.error(errorMessage(e, i18n.t("Couldn't create a verification link"))),
          })
        }
      >
        <MailCheck size={12} aria-hidden />
        <span className="sr-only">{t('Resend verification to {{email}}', { email: user.email })}</span>
      </Button>

      <Button
        variant="ghost"
        size="sm"
        title={t('Change the login email address')}
        onClick={() => setChangingEmail(true)}
      >
        <AtSign size={12} aria-hidden />
        <span className="sr-only">{t('Change email for {{email}}', { email: user.email })}</span>
      </Button>

      {/*
        Greyed out when there is nothing to clear. The list row now carries
        `mfa_enabled` (GL#3), so this can be answered before the click instead
        of from the response after it — the action stays honest either way,
        because `mfa_was_enabled` still reports what actually happened, but an
        operator chasing a lockout should not have to fire a destructive-looking
        action to discover it was a no-op.
      */}
      <Button
        variant="ghost"
        size="sm"
        disabled={clearMfa.isPending || !user.mfa_enabled}
        title={
          user.mfa_enabled
            ? 'Clear MFA for a user locked out of their authenticator'
            : `${user.email} has no MFA configured — nothing to clear`
        }
        onClick={() => setConfirmingMfaReset(true)}
      >
        <ShieldOff size={12} aria-hidden />
        <span className="sr-only">
          {user.mfa_enabled
            ? t('Clear MFA for {{email}}', { email: user.email })
            : t('Clear MFA for {{email}} (no MFA configured)', { email: user.email })}
        </span>
      </Button>

      <ChangeEmailDialog open={changingEmail} onOpenChange={setChangingEmail} user={user} />

      <ConfirmAction
        open={confirmingMfaReset}
        onOpenChange={setConfirmingMfaReset}
        title={t('Clear MFA for {{email}}?', { email: user.email })}
        confirmLabel={t('Clear MFA')}
        pending={clearMfa.isPending}
        consequences={[
          'Turns two-factor authentication off. Only do this once you have confirmed out of band that the person asking really is the account holder — that check is the only one there is.',
          `Signs ${user.email} out on every device: the account's security level just dropped, so tokens minted before it stop working.`,
          'Until they enrol a new authenticator, their password is the only thing standing between anyone and the account.',
        ]}
        onConfirm={() =>
          clearMfa.mutate(user.id, {
            onSuccess: (r) => {
              // `mfa_was_enabled` is the difference between a recovery and a
              // no-op. Reporting both as success would tell the operator they
              // fixed a lockout they did not touch.
              if (r.mfa_was_enabled) {
                toast.success(i18n.t('MFA cleared for {{email}} — they are signed out and can re-enrol', { email: user.email }))
              } else {
                toast.message(i18n.t('MFA was already off for {{email}} — nothing changed', { email: user.email }))
              }
            },
            onError: (e) => toast.error(errorMessage(e, i18n.t("Couldn't clear MFA for this account"))),
            onSettled: () => setConfirmingMfaReset(false),
          })
        }
      />

      {confirmingDelete ? (
        <>
          <Button
            variant="danger"
            size="sm"
            disabled={deleteUser.isPending}
            onClick={() =>
              deleteUser.mutate(user.id, {
                onSuccess: (r) =>
                  toast.success(i18n.t('{{email}} deleted ({{rows}} rows)', { email: user.email, rows: r.rows_deleted })),
                onError: (e) => toast.error(errorMessage(e, i18n.t("Couldn't delete the account"))),
                onSettled: () => setConfirmingDelete(false),
              })
            }
          >
            {deleteUser.isPending ? t('Deleting…') : t('Confirm')}
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setConfirmingDelete(false)}>
            {t('Cancel')}
          </Button>
        </>
      ) : (
        <Button
          variant="ghost"
          size="sm"
          disabled={isSelf}
          title={
            isSelf
              ? 'Delete your own account from Settings > Data & Privacy'
              : 'Permanently delete this user and all their data'
          }
          onClick={() => setConfirmingDelete(true)}
        >
          <Trash2 size={12} aria-hidden />
          <span className="sr-only">{t('Delete {{email}}', { email: user.email })}</span>
        </Button>
      )}
    </div>
  )
}
