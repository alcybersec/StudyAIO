import { Link } from 'react-router-dom'
import { ShieldCheck, UserRound } from 'lucide-react'
import { Badge, Card } from '../../ui'
import { useAuth } from '../../../hooks/useAuth'

/**
 * Account & Security overview. Password changes and MFA management live on
 * the Profile page — this section summarizes the account and links there.
 */
export function AccountSection() {
  const { user, isSelfHosted } = useAuth()

  if (isSelfHosted || !user) {
    return (
      <Card>
        <h2 className="text-[13px] font-semibold text-text mb-2">Account &amp; Security</h2>
        <p className="text-xs text-text-muted max-w-md">
          This instance runs in self-hosted mode — there are no user accounts to manage. All data
          belongs to the local workspace.
        </p>
      </Card>
    )
  }

  return (
    <Card>
      <h2 className="text-[13px] font-semibold text-text mb-4">Account &amp; Security</h2>
      <div className="space-y-4 max-w-md">
        <div className="flex items-center gap-3">
          <span className="w-9 h-9 rounded-lg bg-surface-2 text-text-muted flex items-center justify-center shrink-0">
            <UserRound size={16} aria-hidden />
          </span>
          <div className="min-w-0">
            <p className="text-sm font-medium text-text truncate">{user.username}</p>
            <p className="text-xs text-text-muted truncate">{user.email}</p>
          </div>
          <span className="ml-auto flex items-center gap-1.5">
            <Badge variant={user.tier === 'pro' ? 'success' : 'default'}>{user.tier}</Badge>
            {user.role === 'admin' && <Badge variant="info">admin</Badge>}
          </span>
        </div>

        <div className="flex items-center gap-2 text-xs text-text-muted">
          <ShieldCheck size={14} className={user.mfa_enabled ? 'text-sage-fg' : 'text-text-faint'} aria-hidden />
          {user.mfa_enabled ? 'Two-factor authentication is on' : 'Two-factor authentication is off'}
        </div>

        <p className="text-xs text-text-faint">
          Change your password, manage two-factor authentication, and edit profile details on the{' '}
          <Link to="/profile" className="text-text-muted hover:text-text underline underline-offset-2">
            profile page
          </Link>
          .
        </p>
      </div>
    </Card>
  )
}
