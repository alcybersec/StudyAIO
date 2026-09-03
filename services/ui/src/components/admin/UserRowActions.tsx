import { useState } from 'react'
import { KeyRound, MailCheck, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '../ui'
import {
  useDeleteAdminUser,
  useResendVerification,
  useSendPasswordReset,
} from '../../hooks/useApi'
import type { AdminUser } from '../../types'

interface UserRowActionsProps {
  user: AdminUser
  /** The signed-in admin, who cannot delete themselves from here. */
  currentUserId: string | undefined
}

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof Error && err.message ? err.message : fallback
}

/**
 * Per-user admin actions: password reset, resend verification, delete.
 *
 * Deletion is irreversible and takes every row the user owns with it, so it
 * asks for a second click rather than firing on the first.
 */
export function UserRowActions({ user, currentUserId }: UserRowActionsProps) {
  const [confirmingDelete, setConfirmingDelete] = useState(false)

  const sendReset = useSendPasswordReset()
  const resendVerification = useResendVerification()
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
