import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useAdminUsers, useSystemMetrics, useUpdateAdminUser } from '../hooks/useApi'
import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  PageHeader,
  SectionLabel,
  Select,
  Skeleton,
  Table,
  TBody,
  TCell,
  THead,
  TRow,
} from '../components/ui'
import { toast } from 'sonner'
import type { AdminUser } from '../types'
import { InvitePanel } from '../components/admin/InvitePanel'
import { AddUserForm } from '../components/admin/AddUserForm'
import { UserRowActions } from '../components/admin/UserRowActions'
import { ConfirmAction } from '../components/admin/ConfirmAction'
import { useAuth } from '../hooks/useAuth'

const PAGE_SIZE = 25

const ROLE_OPTIONS = [
  { value: 'user', label: 'user' },
  { value: 'admin', label: 'admin' },
  { value: 'demo', label: 'demo' },
]

const TIER_OPTIONS = [
  { value: 'free', label: 'free' },
  { value: 'pro', label: 'pro' },
]

function MetricCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-surface-1 rounded-xl border border-border p-4">
      <SectionLabel>{label}</SectionLabel>
      <div className="text-2xl font-bold text-text">{value}</div>
    </div>
  )
}

function MetricsGrid() {
  const { data: metrics, isLoading, isError, refetch } = useSystemMetrics()

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="bg-surface-1 rounded-xl border border-border p-4 space-y-2">
            <Skeleton height={10} width={64} />
            <Skeleton height={28} width={48} />
          </div>
        ))}
      </div>
    )
  }

  if (isError && !metrics) {
    return <ErrorState compact title="System metrics couldn't load" onRetry={() => refetch()} />
  }

  if (!metrics) return null

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      <MetricCard label="Users" value={metrics.total_users} />
      <MetricCard label="Courses" value={metrics.total_courses} />
      <MetricCard label="Artifacts" value={metrics.total_artifacts} />
      <MetricCard label="Pipelines 24h" value={metrics.pipeline_runs_24h} />
      <MetricCard label="Storage MB" value={metrics.total_storage_mb.toFixed(1)} />
      <MetricCard label="Storage bytes" value={metrics.total_storage_bytes.toLocaleString()} />
    </div>
  )
}

/** A change held back until the admin has read what it does. */
interface PendingChange {
  field: 'role' | 'is_active'
  value: string | boolean
  title: string
  confirmLabel: string
  consequences: string[]
  /** Reported after the PATCH succeeds, so the sign-out is not silent either. */
  successMessage: string
}

// ── What the inline controls actually do ───────────────────────
//
// A role change and a reactivation both revoke the user's sessions (#88), and
// both are fired from a control that commits on change — a dropdown pick, or a
// single click on a badge. Until now the admin was told nothing, before or
// after, and a stray click was enough.
//
// The tier select deliberately gets no confirmation: a tier moves a quota, not
// a privilege, and nothing in a token depends on it. Confirming everything is
// how a confirmation stops being read.

function describeRoleChange(user: AdminUser, role: string): PendingChange {
  const consequences = [
    `Signs ${user.email} out on every device immediately — their access token and their 7-day refresh token both stop working, so they have to sign in again.`,
  ]
  if (role === 'demo') {
    consequences.push('A demo account cannot write: their next session is read-only.')
  }
  if (role === 'admin') {
    consequences.push(
      'An admin can read and change every account on this instance, including yours.',
    )
  }
  if (user.role === 'admin' && role !== 'admin') {
    consequences.push(
      'They lose admin access. If this is the last admin account, the change is refused rather than locking everyone out.',
    )
  }
  return {
    field: 'role',
    value: role,
    title: `Change ${user.email} from ${user.role} to ${role}?`,
    confirmLabel: `Change role to ${role}`,
    consequences,
    successMessage: `${user.email} is now ${role} — signed out on every device.`,
  }
}

function describeStatusChange(user: AdminUser): PendingChange {
  if (user.is_active) {
    return {
      field: 'is_active',
      value: false,
      title: `Deactivate ${user.email}?`,
      confirmLabel: 'Deactivate',
      consequences: [
        `Every request from this account is refused while it is inactive, a token refresh included, and ${user.email} cannot sign in again.`,
        'Nothing is deleted, and their sessions are suspended rather than revoked — but reactivating the account later revokes them for real.',
      ],
      successMessage: `${user.email} deactivated.`,
    }
  }
  return {
    field: 'is_active',
    value: true,
    title: `Reactivate ${user.email}?`,
    confirmLabel: 'Reactivate',
    consequences: [
      `Restores access for ${user.email}.`,
      'Signs them out on every device first: every session from before the deactivation is revoked, including the 7-day refresh token, so they sign in fresh rather than resuming where they left off.',
    ],
    successMessage: `${user.email} reactivated — the sessions it had before are revoked.`,
  }
}

function UserRow({
  user,
  onUpdate,
  currentUserId,
}: {
  user: AdminUser
  onUpdate: (
    id: string,
    change: { field: string; value: string | boolean; successMessage?: string },
  ) => void
  currentUserId: string | undefined
}) {
  const navigate = useNavigate()
  const [pending, setPending] = useState<PendingChange | null>(null)

  return (
    <TRow onClick={() => navigate(`/admin/users/${user.id}`)}>
      <TCell className="text-text">{user.email}</TCell>
      <TCell className="text-text-muted">{user.username ?? '—'}</TCell>
      <TCell>
        <div onClick={(e) => e.stopPropagation()} className="w-24">
          <Select
            options={ROLE_OPTIONS}
            value={user.role}
            onValueChange={(v) => {
              // A pick that matches the stored role changes nothing and revokes
              // nothing, so it must not raise a dialog claiming otherwise.
              if (v !== user.role) setPending(describeRoleChange(user, v))
            }}
          />
        </div>
      </TCell>
      <TCell>
        <div onClick={(e) => e.stopPropagation()} className="w-24">
          <Select
            options={TIER_OPTIONS}
            value={user.tier}
            onValueChange={(v) => onUpdate(user.id, { field: 'tier', value: v })}
          />
        </div>
      </TCell>
      <TCell>
        <button
          onClick={(e) => {
            e.stopPropagation()
            setPending(describeStatusChange(user))
          }}
          className="cursor-pointer"
          aria-label={user.is_active ? 'Deactivate user' : 'Activate user'}
        >
          <Badge variant={user.is_active ? 'success' : 'danger'}>{user.is_active ? 'active' : 'inactive'}</Badge>
        </button>
      </TCell>
      <TCell className="font-mono text-[11px] text-text-faint">
        {user.created_at ? new Date(user.created_at).toLocaleDateString() : '—'}
      </TCell>
      <TCell className="font-mono text-[11px] text-text-faint">
        {user.last_login_at ? new Date(user.last_login_at).toLocaleDateString() : 'never'}
      </TCell>
      <TCell>
        <UserRowActions user={user} currentUserId={currentUserId} />
        {/* Shared by the role select and the status badge, and rendered here
            only because a row has to render it somewhere: the dialog is
            portalled to the body, so its position in the table is immaterial. */}
        {pending && (
          <ConfirmAction
            open
            onOpenChange={(open) => {
              if (!open) setPending(null)
            }}
            title={pending.title}
            consequences={pending.consequences}
            confirmLabel={pending.confirmLabel}
            onConfirm={() => {
              onUpdate(user.id, pending)
              setPending(null)
            }}
          />
        )}
      </TCell>
    </TRow>
  )
}

function UsersSkeleton() {
  return (
    <div className="p-4 space-y-3" role="status" aria-label="Loading users">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="flex items-center gap-4">
          <Skeleton height={14} width="30%" />
          <Skeleton height={14} width="15%" />
          <Skeleton height={22} width={80} />
          <Skeleton height={22} width={80} />
          <Skeleton height={18} width={56} rounded />
        </div>
      ))}
    </div>
  )
}

export function AdminPage() {
  const [page, setPage] = useState(0)
  const [roleFilter, setRoleFilter] = useState<string>('all')
  const [tierFilter, setTierFilter] = useState<string>('all')

  const {
    data: usersData,
    isLoading: usersLoading,
    isError: usersError,
    refetch: refetchUsers,
  } = useAdminUsers({
    role: roleFilter === 'all' ? undefined : roleFilter,
    tier: tierFilter === 'all' ? undefined : tierFilter,
    offset: page * PAGE_SIZE,
    limit: PAGE_SIZE,
  })
  const updateUser = useUpdateAdminUser()
  const { user: currentUser } = useAuth()

  /**
   * One field per PATCH, as before — but no longer silent either way.
   *
   * A failure used to vanish: demoting the last admin is refused with a 422
   * (`_guard_last_admin`), and the only sign of it was the select snapping back.
   * And a success that ends every one of the user's sessions deserves to be
   * said out loud.
   *
   * The success line is derived from the change we asked for, not from the
   * response: `UserResponse` does not carry whether sessions were revoked, even
   * though `admin_service` knows and logs it (`sessions_revoked=`). Adding that
   * field would let this report the server's answer instead of inferring it.
   */
  const handleUpdate = (
    userId: string,
    change: { field: string; value: string | boolean; successMessage?: string },
  ) => {
    updateUser.mutate(
      { userId, data: { [change.field]: change.value } },
      {
        onSuccess: () => {
          if (change.successMessage) toast.success(change.successMessage)
        },
        onError: (err: unknown) =>
          toast.error(
            err instanceof Error && err.message ? err.message : "Couldn't update this account",
          ),
      },
    )
  }

  const totalPages = usersData ? Math.ceil(usersData.total / PAGE_SIZE) : 0

  return (
    <div className="space-y-6">
      <PageHeader title="Admin" subtitle="System metrics and user management" />

      <MetricsGrid />

      <InvitePanel />

      <div className="bg-surface-1 rounded-xl border border-border">
        <div className="flex flex-wrap items-center gap-3 p-4 border-b border-border">
          <h2 className="text-sm font-semibold text-text">Users</h2>
          <div className="flex-1" />
          <Select
            className="w-32"
            options={[{ value: 'all', label: 'All roles' }, ...ROLE_OPTIONS]}
            value={roleFilter}
            onValueChange={(v) => {
              setRoleFilter(v)
              setPage(0)
            }}
          />
          <Select
            className="w-32"
            options={[{ value: 'all', label: 'All tiers' }, ...TIER_OPTIONS]}
            value={tierFilter}
            onValueChange={(v) => {
              setTierFilter(v)
              setPage(0)
            }}
          />
        </div>

        <AddUserForm />

        {usersLoading && !usersData ? (
          <UsersSkeleton />
        ) : usersError && !usersData ? (
          <div className="p-4">
            <ErrorState compact title="Users couldn't load" onRetry={() => refetchUsers()} />
          </div>
        ) : usersData && usersData.users.length > 0 ? (
          <>
            <div className="px-4">
              <Table>
                <THead>
                  <TCell header>Email</TCell>
                  <TCell header>Username</TCell>
                  <TCell header>Role</TCell>
                  <TCell header>Tier</TCell>
                  <TCell header>Status</TCell>
                  <TCell header>Created</TCell>
                  <TCell header>Last login</TCell>
                  <TCell header>Actions</TCell>
                </THead>
                <TBody>
                  {usersData.users.map((user) => (
                    <UserRow
                      key={user.id}
                      user={user}
                      onUpdate={handleUpdate}
                      currentUserId={currentUser?.id}
                    />
                  ))}
                </TBody>
              </Table>
            </div>

            {totalPages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-border">
                <span className="text-[11px] font-mono text-text-faint">
                  {usersData.total} user{usersData.total !== 1 ? 's' : ''} · page {page + 1}/{totalPages}
                </span>
                <div className="flex items-center gap-2">
                  <Button variant="secondary" size="sm" onClick={() => setPage(page - 1)} disabled={page === 0}>
                    <ChevronLeft size={13} aria-hidden /> Prev
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setPage(page + 1)}
                    disabled={page + 1 >= totalPages}
                  >
                    Next <ChevronRight size={13} aria-hidden />
                  </Button>
                </div>
              </div>
            )}
          </>
        ) : (
          <EmptyState
            compact
            title="No users match these filters"
            description="Try clearing the role or tier filter."
          />
        )}
      </div>
    </div>
  )
}
