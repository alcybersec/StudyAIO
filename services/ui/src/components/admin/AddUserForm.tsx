import { useState } from 'react'
import { Check, Copy, UserPlus } from 'lucide-react'
import { toast } from 'sonner'
import { Button, Input, Select } from '../ui'
import { useCreateAdminUser } from '../../hooks/useApi'
import type { AdminUserCreated } from '../../types'

const ROLE_OPTIONS = [
  { value: 'user', label: 'User' },
  { value: 'admin', label: 'Admin' },
]

const TIER_OPTIONS = [
  { value: 'free', label: 'Free' },
  { value: 'pro', label: 'Pro' },
]

/**
 * The set-password link for a freshly created account.
 *
 * Shown whether or not the email went out: a beta instance often has no SMTP,
 * and an admin who cannot deliver the link cannot onboard anyone.
 */
function SetupLink({ result, onDismiss }: { result: AdminUserCreated; onDismiss: () => void }) {
  const [copied, setCopied] = useState(false)

  return (
    <div className="p-3 rounded-lg bg-sage-soft border border-sage/30 space-y-2">
      <p className="text-xs text-text">
        <span className="font-medium">{result.user.email}</span> created.{' '}
        {result.email_sent
          ? 'The set-password link was emailed to them.'
          : 'No email was sent — send them this link yourself:'}
      </p>
      <div className="flex items-center gap-2">
        <code className="flex-1 min-w-0 truncate text-[11px] font-mono text-text-muted bg-surface-2 rounded px-2 py-1.5">
          {result.setup_url}
        </code>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => {
            void navigator.clipboard
              .writeText(result.setup_url)
              .then(() => {
                setCopied(true)
                setTimeout(() => setCopied(false), 1500)
              })
              .catch(() => toast.error('Could not copy to clipboard'))
          }}
        >
          {copied ? <Check size={12} aria-hidden /> : <Copy size={12} aria-hidden />}
          {copied ? 'Copied' : 'Copy'}
        </Button>
      </div>
      <p className="text-[11px] text-text-faint">
        Single use, expires in 24 hours. It is not shown again once dismissed.
      </p>
      <Button variant="ghost" size="sm" onClick={onDismiss}>
        Dismiss
      </Button>
    </div>
  )
}

/** Create an account and surface its one-time setup link. Admin only. */
export function AddUserForm() {
  const [open, setOpen] = useState(false)
  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [role, setRole] = useState('user')
  const [tier, setTier] = useState('free')
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<AdminUserCreated | null>(null)

  const createUser = useCreateAdminUser()

  const reset = () => {
    setEmail('')
    setUsername('')
    setRole('user')
    setTier('free')
    setError(null)
  }

  if (!open) {
    return (
      <div className="p-4 border-b border-border">
        <Button size="sm" onClick={() => setOpen(true)}>
          <UserPlus size={12} aria-hidden /> Add user
        </Button>
        {result && (
          <div className="mt-3">
            <SetupLink result={result} onDismiss={() => setResult(null)} />
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="p-4 border-b border-border space-y-3">
      <div className="flex flex-wrap items-end gap-3">
        <Input
          id="new-user-email"
          label="Email"
          type="email"
          placeholder="tester@example.com"
          className="w-56"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <Input
          id="new-user-username"
          label="Username"
          placeholder="tester"
          className="w-40"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        <div className="w-28">
          <label htmlFor="new-user-role" className="block text-xs text-text-muted mb-1.5">
            Role
          </label>
          <Select options={ROLE_OPTIONS} value={role} onValueChange={setRole} />
        </div>
        <div className="w-28">
          <label htmlFor="new-user-tier" className="block text-xs text-text-muted mb-1.5">
            Tier
          </label>
          <Select options={TIER_OPTIONS} value={tier} onValueChange={setTier} />
        </div>
        <Button
          size="sm"
          disabled={createUser.isPending || !email.trim() || username.trim().length < 3}
          onClick={() => {
            setError(null)
            createUser.mutate(
              { email: email.trim(), username: username.trim(), role, tier },
              {
                onSuccess: (created) => {
                  setResult(created)
                  setOpen(false)
                  reset()
                },
                onError: (err: unknown) => {
                  setError(
                    err instanceof Error && err.message
                      ? err.message
                      : 'Could not create the account',
                  )
                },
              },
            )
          }}
        >
          {createUser.isPending ? 'Creating…' : 'Create'}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            setOpen(false)
            reset()
          }}
        >
          Cancel
        </Button>
      </div>

      <p className="text-[11px] text-text-faint">
        No password is set. The new user gets a single-use link to choose their own.
      </p>

      {error && (
        <p role="alert" className="text-xs text-red-fg">
          {error}
        </p>
      )}
    </div>
  )
}
