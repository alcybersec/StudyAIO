import { useState } from 'react'
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
      .then(() => toast.success('No email configured — link copied to clipboard'))
      .catch(() => toast.message('No email configured. Link:', { description: url }))
  }

  return (
    <div className="flex items-center justify-end gap-1" onClick={(e) => e.stopPropagation()}>
      <Button
        variant="ghost"
        size="sm"
        disabled={sendReset.isPending}
        title="Send a password reset link"
        onClick={() =>
          sendReset.mutate(user.id, {
            onSuccess: (r) => showLink(r.url, r.email_sent, 'Password reset emailed'),
            onError: (e) => toast.error(errorMessage(e, "Couldn't create a reset link")),
          })
        }
      >
        <KeyRound size={12} aria-hidden />
        <span className="sr-only">Send password reset to {user.email}</span>
      </Button>

      <Button
        variant="ghost"
        size="sm"
        disabled={resendVerification.isPending}
        title="Resend the verification email"
        onClick={() =>
          resendVerification.mutate(user.id, {
            onSuccess: (r) => showLink(r.url, r.email_sent, 'Verification email sent'),
            onError: (e) => toast.error(errorMessage(e, "Couldn't create a verification link")),
          })
        }
      >
        <MailCheck size={12} aria-hidden />
        <span className="sr-only">Resend verification to {user.email}</span>
      </Button>

      <Button
        variant="ghost"
        size="sm"
        title="Change the login email address"
        onClick={() => setChangingEmail(true)}
      >
        <AtSign size={12} aria-hidden />
        <span className="sr-only">Change email for {user.email}</span>
      </Button>

      <Button
        variant="ghost"
        size="sm"
        disabled={clearMfa.isPending}
        title="Clear MFA for a user locked out of their authenticator"
        onClick={() => setConfirmingMfaReset(true)}
      >
        <ShieldOff size={12} aria-hidden />
        <span className="sr-only">Clear MFA for {user.email}</span>
      </Button>

      <ChangeEmailDialog open={changingEmail} onOpenChange={setChangingEmail} user={user} />

      <ConfirmAction
        open={confirmingMfaReset}
        onOpenChange={setConfirmingMfaReset}
        title={`Clear MFA for ${user.email}?`}
        confirmLabel="Clear MFA"
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
                toast.success(`MFA cleared for ${user.email} — they are signed out and can re-enrol`)
              } else {
                toast.message(`MFA was already off for ${user.email} — nothing changed`)
              }
            },
            onError: (e) => toast.error(errorMessage(e, "Couldn't clear MFA for this account")),
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
                  toast.success(`${user.email} deleted (${r.rows_deleted} rows)`),
                onError: (e) => toast.error(errorMessage(e, "Couldn't delete the account")),
                onSettled: () => setConfirmingDelete(false),
              })
            }
          >
            {deleteUser.isPending ? 'Deleting…' : 'Confirm'}
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setConfirmingDelete(false)}>
            Cancel
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
          <span className="sr-only">Delete {user.email}</span>
        </Button>
      )}
    </div>
  )
}
