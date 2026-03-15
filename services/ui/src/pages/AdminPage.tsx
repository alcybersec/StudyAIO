import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAdminUsers, useSystemMetrics, useUpdateAdminUser } from '../hooks/useApi'
import { ErrorBanner } from '../components/ui/ErrorBanner'
import type { AdminUser } from '../types'

function MetricCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-surface rounded-xl border border-border p-5">
      <div className="text-sm text-text-muted">{label}</div>
      <div className="text-2xl font-bold text-text mt-1">{value}</div>
    </div>
  )
}

function UserRow({ user, onUpdate }: { user: AdminUser; onUpdate: (id: string, field: string, value: string | boolean) => void }) {
  const navigate = useNavigate()
  return (
    <tr
      className="border-b border-border last:border-b-0 hover:bg-surface-alt/50 transition-colors cursor-pointer"
      onClick={() => navigate(`/admin/users/${user.id}`)}
    >
      <td className="px-4 py-3 text-sm text-text">{user.email}</td>
      <td className="px-4 py-3 text-sm text-text">{user.username ?? '—'}</td>
      <td className="px-4 py-3">
        <select
          value={user.role}
          onChange={(e) => onUpdate(user.id, 'role', e.target.value)}
          onClick={(e) => e.stopPropagation()}
          className="text-xs px-2 py-1 rounded-md bg-surface border border-border text-text"
        >
          <option value="user">user</option>
          <option value="admin">admin</option>
          <option value="demo">demo</option>
        </select>
      </td>
      <td className="px-4 py-3">
        <select
          value={user.tier}
          onChange={(e) => onUpdate(user.id, 'tier', e.target.value)}
          onClick={(e) => e.stopPropagation()}
          className="text-xs px-2 py-1 rounded-md bg-surface border border-border text-text"
        >
          <option value="free">free</option>
          <option value="pro">pro</option>
        </select>
      </td>
      <td className="px-4 py-3 text-center">
        <button
          onClick={(e) => { e.stopPropagation(); onUpdate(user.id, 'is_active', !user.is_active) }}
          className={`text-xs px-2 py-0.5 rounded-full font-medium ${
            user.is_active
              ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
              : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
          }`}
        >
          {user.is_active ? 'Active' : 'Inactive'}
        </button>
      </td>
      <td className="px-4 py-3 text-xs text-text-muted">
        {user.created_at ? new Date(user.created_at).toLocaleDateString() : '—'}
      </td>
      <td className="px-4 py-3 text-xs text-text-muted">
        {user.last_login_at ? new Date(user.last_login_at).toLocaleDateString() : 'Never'}
      </td>
    </tr>
  )
}

export function AdminPage() {
  const [page, setPage] = useState(0)
  const [roleFilter, setRoleFilter] = useState<string>('')
  const [tierFilter, setTierFilter] = useState<string>('')
  const pageSize = 25

  const { data: metrics, isLoading: metricsLoading, error: metricsError, refetch: refetchMetrics } = useSystemMetrics()
  const { data: usersData, isLoading: usersLoading, error: usersError, refetch: refetchUsers } = useAdminUsers({
    role: roleFilter || undefined,
    tier: tierFilter || undefined,
    offset: page * pageSize,
    limit: pageSize,
  })
  const updateUser = useUpdateAdminUser()

  const handleUpdate = (userId: string, field: string, value: string | boolean) => {
    updateUser.mutate({ userId, data: { [field]: value } })
  }

  const totalPages = usersData ? Math.ceil(usersData.total / pageSize) : 0

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-text">Admin Dashboard</h1>

      {metricsError && (
        <ErrorBanner message="Failed to load system metrics." onRetry={() => refetchMetrics()} />
      )}
      {usersError && (
        <ErrorBanner message="Failed to load users." onRetry={() => refetchUsers()} />
      )}

      {/* Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {metricsLoading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="bg-surface rounded-xl border border-border p-5 animate-pulse">
              <div className="h-4 bg-surface-alt rounded w-16 mb-2" />
              <div className="h-7 bg-surface-alt rounded w-12" />
            </div>
          ))
        ) : metrics ? (
          <>
            <MetricCard label="Total Users" value={metrics.total_users} />
            <MetricCard label="Courses" value={metrics.total_courses} />
            <MetricCard label="Artifacts" value={metrics.total_artifacts} />
            <MetricCard label="Pipelines (24h)" value={metrics.pipeline_runs_24h} />
            <MetricCard label="Storage" value={`${metrics.total_storage_mb.toFixed(1)} MB`} />
            <MetricCard label="Storage (bytes)" value={metrics.total_storage_bytes.toLocaleString()} />
          </>
        ) : null}
      </div>

      {/* User Management */}
      <div className="bg-surface rounded-xl border border-border">
        <div className="flex flex-wrap items-center gap-3 p-4 border-b border-border">
          <h2 className="text-lg font-semibold text-text">Users</h2>
          <div className="flex-1" />
          <select
            value={roleFilter}
            onChange={(e) => { setRoleFilter(e.target.value); setPage(0) }}
            className="text-sm px-3 py-1.5 rounded-lg bg-surface border border-border text-text"
          >
            <option value="">All Roles</option>
            <option value="admin">Admin</option>
            <option value="user">User</option>
            <option value="demo">Demo</option>
          </select>
          <select
            value={tierFilter}
            onChange={(e) => { setTierFilter(e.target.value); setPage(0) }}
            className="text-sm px-3 py-1.5 rounded-lg bg-surface border border-border text-text"
          >
            <option value="">All Tiers</option>
            <option value="free">Free</option>
            <option value="pro">Pro</option>
          </select>
        </div>

        {usersLoading ? (
          <div className="p-8 text-center text-text-muted">Loading users...</div>
        ) : usersData && usersData.users.length > 0 ? (
          <>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border bg-surface-alt/50">
                    <th className="px-4 py-2 text-left text-xs font-semibold text-text-muted uppercase">Email</th>
                    <th className="px-4 py-2 text-left text-xs font-semibold text-text-muted uppercase">Username</th>
                    <th className="px-4 py-2 text-left text-xs font-semibold text-text-muted uppercase">Role</th>
                    <th className="px-4 py-2 text-left text-xs font-semibold text-text-muted uppercase">Tier</th>
                    <th className="px-4 py-2 text-center text-xs font-semibold text-text-muted uppercase">Status</th>
                    <th className="px-4 py-2 text-left text-xs font-semibold text-text-muted uppercase">Created</th>
                    <th className="px-4 py-2 text-left text-xs font-semibold text-text-muted uppercase">Last Login</th>
                  </tr>
                </thead>
                <tbody>
                  {usersData.users.map((user) => (
                    <UserRow key={user.id} user={user} onUpdate={handleUpdate} />
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-border">
                <span className="text-sm text-text-muted">
                  {usersData.total} user{usersData.total !== 1 ? 's' : ''} total
                </span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPage(page - 1)}
                    disabled={page === 0}
                    className="px-3 py-1 text-sm rounded-md border border-border text-text disabled:opacity-40 hover:bg-surface-alt transition-colors"
                  >
                    Prev
                  </button>
                  <span className="text-sm text-text-muted">
                    Page {page + 1} of {totalPages}
                  </span>
                  <button
                    onClick={() => setPage(page + 1)}
                    disabled={page + 1 >= totalPages}
                    className="px-3 py-1 text-sm rounded-md border border-border text-text disabled:opacity-40 hover:bg-surface-alt transition-colors"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </>
        ) : (
          <div className="p-8 text-center text-text-muted">No users found.</div>
        )}
      </div>
    </div>
  )
}
