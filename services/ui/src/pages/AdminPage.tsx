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
import type { AdminUser } from '../types'
import { InvitePanel } from '../components/admin/InvitePanel'

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

function UserRow({ user, onUpdate }: { user: AdminUser; onUpdate: (id: string, field: string, value: string | boolean) => void }) {
  const navigate = useNavigate()
  return (
    <TRow onClick={() => navigate(`/admin/users/${user.id}`)}>
      <TCell className="text-text">{user.email}</TCell>
      <TCell className="text-text-muted">{user.username ?? '—'}</TCell>
      <TCell>
        <div onClick={(e) => e.stopPropagation()} className="w-24">
          <Select options={ROLE_OPTIONS} value={user.role} onValueChange={(v) => onUpdate(user.id, 'role', v)} />
        </div>
      </TCell>
      <TCell>
        <div onClick={(e) => e.stopPropagation()} className="w-24">
          <Select options={TIER_OPTIONS} value={user.tier} onValueChange={(v) => onUpdate(user.id, 'tier', v)} />
        </div>
      </TCell>
      <TCell>
        <button
          onClick={(e) => {
            e.stopPropagation()
            onUpdate(user.id, 'is_active', !user.is_active)
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

  const handleUpdate = (userId: string, field: string, value: string | boolean) => {
    updateUser.mutate({ userId, data: { [field]: value } })
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
                </THead>
                <TBody>
                  {usersData.users.map((user) => (
                    <UserRow key={user.id} user={user} onUpdate={handleUpdate} />
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
