import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Download, TriangleAlert } from 'lucide-react'
import { toast } from 'sonner'
import { Button, Card, Input } from '../../ui'
import { authApi } from '../../../api/auth'
import { useAuth } from '../../../hooks/useAuth'

/**
 * Data & Privacy: download everything this account owns, or delete it.
 *
 * Deletion is immediate and unrecoverable, so it is deliberately awkward —
 * an explicit reveal, then re-authentication, before the button appears.
 */
export function DataPrivacySection() {
  const { user, isSelfHosted } = useAuth()
  const [confirming, setConfirming] = useState(false)
  const [password, setPassword] = useState('')
  const [confirmUsername, setConfirmUsername] = useState('')
  const [error, setError] = useState<string | null>(null)

  // OAuth-only accounts have no password to re-enter.
  const hasPassword = !isSelfHosted && user != null && user.has_password !== false

  const exportMutation = useMutation({
    mutationFn: authApi.exportData,
    onSuccess: (data) => {
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `studyaio-export-${new Date().toISOString().slice(0, 10)}.json`
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
      toast.success('Your data has been downloaded')
    },
    onError: () => toast.error("Couldn't export your data. Please try again."),
  })

  const deleteMutation = useMutation({
    mutationFn: authApi.deleteAccount,
    onSuccess: () => {
      // The server has already cleared the auth cookies; a full reload drops
      // every cached query rather than leaving a deleted user's data on screen.
      window.location.href = '/login?reason=account_deleted'
    },
    onError: (err: unknown) => {
      setError(
        err instanceof Error && err.message
          ? err.message
          : 'Could not delete your account. Please try again.',
      )
    },
  })

  if (isSelfHosted || !user) {
    return (
      <Card>
        <h2 className="text-[13px] font-semibold text-text mb-2">Data &amp; Privacy</h2>
        <p className="text-xs text-text-muted max-w-md">
          This instance runs in self-hosted mode — your data already lives entirely on your own
          machine, under the <code className="text-text-faint">data/</code> directory.
        </p>
      </Card>
    )
  }

  const canDelete = hasPassword ? password.length > 0 : confirmUsername === user.username

  return (
    <Card>
      <h2 className="text-[13px] font-semibold text-text mb-4">Data &amp; Privacy</h2>

      <div className="space-y-6 max-w-md">
        <div>
          <p className="text-sm font-medium text-text mb-1">Export your data</p>
          <p className="text-xs text-text-muted mb-3">
            Download every course, lecture, summary, flashcard and study record on this account as
            a single JSON file.
          </p>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => exportMutation.mutate()}
            disabled={exportMutation.isPending}
          >
            <Download size={12} aria-hidden />
            {exportMutation.isPending ? 'Preparing…' : 'Download my data'}
          </Button>
        </div>

        <div className="pt-5 border-t border-border">
          <p className="text-sm font-medium text-text mb-1">Delete your account</p>
          <p className="text-xs text-text-muted mb-3">
            Permanently deletes your account, every file you have uploaded, and everything
            generated from them. This happens immediately and cannot be undone.
          </p>

          {!confirming ? (
            <Button variant="danger" size="sm" onClick={() => setConfirming(true)}>
              Delete my account
            </Button>
          ) : (
            <div className="space-y-3 p-3 rounded-lg bg-red-soft border border-red/30">
              <p className="flex items-start gap-2 text-xs text-red-fg">
                <TriangleAlert size={14} className="mt-px shrink-0" aria-hidden />
                <span>
                  This is permanent. Consider downloading your data first — it cannot be recovered
                  afterwards.
                </span>
              </p>

              {hasPassword ? (
                <Input
                  id="delete-password"
                  type="password"
                  label="Confirm your password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  error={error ?? undefined}
                />
              ) : (
                <Input
                  id="delete-confirm-username"
                  type="text"
                  label={`Type "${user.username}" to confirm`}
                  autoComplete="off"
                  value={confirmUsername}
                  onChange={(e) => setConfirmUsername(e.target.value)}
                  error={error ?? undefined}
                />
              )}

              <div className="flex gap-2">
                <Button
                  variant="danger"
                  size="sm"
                  disabled={!canDelete || deleteMutation.isPending}
                  onClick={() => {
                    setError(null)
                    deleteMutation.mutate(
                      hasPassword ? { password } : { confirm_username: confirmUsername },
                    )
                  }}
                >
                  {deleteMutation.isPending ? 'Deleting…' : 'Permanently delete'}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setConfirming(false)
                    setPassword('')
                    setConfirmUsername('')
                    setError(null)
                  }}
                >
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </Card>
  )
}
