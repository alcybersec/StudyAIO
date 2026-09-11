import { MemoryRouter } from 'react-router-dom'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AdminPage } from './AdminPage'
import { useAdminUsers, useSystemMetrics, useUpdateAdminUser } from '../hooks/useApi'

vi.mock('../hooks/useApi', () => ({
  useAdminUsers: vi.fn(),
  useSystemMetrics: vi.fn(),
  useUpdateAdminUser: vi.fn(),
  // The invite panel is exercised in its own tests; here it just needs to render.
  useInvites: vi.fn(() => ({ data: undefined, isLoading: false, isError: false, refetch: vi.fn() })),
  useCreateInvite: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useRevokeInvite: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  // User provisioning is exercised in its own tests; here it just needs to render.
  useCreateAdminUser: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useDeleteAdminUser: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useSendPasswordReset: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useResendVerification: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useClearUserMfa: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
}))

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => ({ user: { id: 'admin-001', email: 'admin@example.com' } }),
}))

const mockUsers = vi.mocked(useAdminUsers)
const mockMetrics = vi.mocked(useSystemMetrics)
const mockUpdate = vi.mocked(useUpdateAdminUser)

const asResult = (q: object) => q as never

const sampleUser = {
  id: 'u1',
  email: 'alice@example.com',
  username: 'alice',
  role: 'user',
  tier: 'free',
  is_active: true,
  created_at: '2026-01-01T00:00:00',
  last_login_at: null,
}

const metricsData = {
  total_users: 4,
  total_courses: 2,
  total_artifacts: 10,
  pipeline_runs_24h: 3,
  total_storage_bytes: 1024,
  total_storage_mb: 0.001,
}

beforeEach(() => {
  vi.clearAllMocks()
  mockUpdate.mockReturnValue(asResult({ mutate: vi.fn(), isPending: false }))
})

function renderPage() {
  return render(
    <MemoryRouter>
      <AdminPage />
    </MemoryRouter>,
  )
}

describe('AdminPage section isolation', () => {
  it('shows metrics ErrorState while the user table still renders data', () => {
    mockMetrics.mockReturnValue(asResult({ data: undefined, isLoading: false, isError: true, refetch: vi.fn() }))
    mockUsers.mockReturnValue(
      asResult({
        data: { users: [sampleUser], total: 1, offset: 0, limit: 25 },
        isLoading: false,
        isError: false,
        refetch: vi.fn(),
      }),
    )

    renderPage()

    const alert = screen.getByRole('alert')
    expect(within(alert).getByText(/system metrics couldn't load/i)).toBeInTheDocument()
    expect(screen.getByText('alice@example.com')).toBeInTheDocument()
  })

  it('retries only the metrics query from the metrics ErrorState', async () => {
    const user = userEvent.setup()
    const refetchMetrics = vi.fn()
    const refetchUsers = vi.fn()
    mockMetrics.mockReturnValue(asResult({ data: undefined, isLoading: false, isError: true, refetch: refetchMetrics }))
    mockUsers.mockReturnValue(
      asResult({
        data: { users: [sampleUser], total: 1, offset: 0, limit: 25 },
        isLoading: false,
        isError: false,
        refetch: refetchUsers,
      }),
    )

    renderPage()
    await user.click(screen.getByRole('button', { name: /retry/i }))

    expect(refetchMetrics).toHaveBeenCalledTimes(1)
    expect(refetchUsers).not.toHaveBeenCalled()
  })

  it('shows an EmptyState when no users match the filters', () => {
    mockMetrics.mockReturnValue(asResult({ data: metricsData, isLoading: false, isError: false, refetch: vi.fn() }))
    mockUsers.mockReturnValue(
      asResult({
        data: { users: [], total: 0, offset: 0, limit: 25 },
        isLoading: false,
        isError: false,
        refetch: vi.fn(),
      }),
    )

    renderPage()
    expect(screen.getByText(/no users match these filters/i)).toBeInTheDocument()
  })

  it('toggling the status badge sends an is_active update once confirmed', async () => {
    const { user, mutate } = setupRow()

    await user.click(screen.getByRole('button', { name: /deactivate user/i }))
    await user.click(screen.getByRole('button', { name: /^deactivate$/i }))

    expect(mutate).toHaveBeenCalledWith({ userId: 'u1', data: { is_active: false } }, expect.anything())
  })
})

// ── Destructive inline controls ────────────────────────────────
//
// Role change and reactivation revoke the user's sessions (#88) and are fired
// from controls that commit on change. These tests exist to pin the gap between
// the click and the PATCH: with the ConfirmAction removed, every "fires
// nothing" assertion below fails, because the mutation runs on the first click.

function setupRow(overrides: Partial<typeof sampleUser> = {}) {
  const mutate = vi.fn()
  mockUpdate.mockReturnValue(asResult({ mutate, isPending: false }))
  mockMetrics.mockReturnValue(asResult({ data: metricsData, isLoading: false, isError: false, refetch: vi.fn() }))
  mockUsers.mockReturnValue(
    asResult({
      data: { users: [{ ...sampleUser, ...overrides }], total: 1, offset: 0, limit: 25 },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    }),
  )
  renderPage()
  return { user: userEvent.setup(), mutate }
}

async function pickRole(user: ReturnType<typeof userEvent.setup>, from: string, to: string) {
  await user.click(screen.getByRole('button', { name: from }))
  await user.click(await screen.findByRole('menuitemradio', { name: to }))
}

describe('AdminPage destructive confirmations', () => {
  it('deactivating asks first and sends nothing on the click itself', async () => {
    const { user, mutate } = setupRow()

    await user.click(screen.getByRole('button', { name: /deactivate user/i }))

    expect(mutate).not.toHaveBeenCalled()
    expect(screen.getByRole('dialog')).toHaveTextContent(/deactivate alice@example.com\?/i)
  })

  it('cancelling a deactivation sends nothing', async () => {
    const { user, mutate } = setupRow()

    await user.click(screen.getByRole('button', { name: /deactivate user/i }))
    await user.click(screen.getByRole('button', { name: /cancel/i }))

    expect(mutate).not.toHaveBeenCalled()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('says that reactivating revokes the sessions the account had before', async () => {
    const { user, mutate } = setupRow({ is_active: false })

    await user.click(screen.getByRole('button', { name: /activate user/i }))

    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveTextContent(/signs them out on every device first/i)
    expect(dialog).toHaveTextContent(/revoked/i)
    expect(dialog).toHaveTextContent(/7-day refresh token/i)
    expect(mutate).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: /^reactivate$/i }))
    expect(mutate).toHaveBeenCalledWith({ userId: 'u1', data: { is_active: true } }, expect.anything())
  })

  it('a role change names the sign-out before it happens', async () => {
    const { user, mutate } = setupRow()

    await pickRole(user, 'user', 'demo')

    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveTextContent(/change alice@example.com from user to demo\?/i)
    expect(dialog).toHaveTextContent(/signs alice@example.com out on every device/i)
    expect(dialog).toHaveTextContent(/read-only/i)
    expect(mutate).not.toHaveBeenCalled()
  })

  it('cancelling a role change sends nothing', async () => {
    const { user, mutate } = setupRow()

    await pickRole(user, 'user', 'admin')
    await user.click(screen.getByRole('button', { name: /cancel/i }))

    expect(mutate).not.toHaveBeenCalled()
  })

  it('confirming a role change sends exactly that field', async () => {
    const { user, mutate } = setupRow()

    await pickRole(user, 'user', 'demo')
    await user.click(screen.getByRole('button', { name: /change role to demo/i }))

    expect(mutate).toHaveBeenCalledWith({ userId: 'u1', data: { role: 'demo' } }, expect.anything())
  })

  it('warns a demotion that it may be refused as the last admin', async () => {
    const { user } = setupRow({ role: 'admin' })

    await pickRole(user, 'admin', 'user')

    expect(screen.getByRole('dialog')).toHaveTextContent(/last admin account/i)
  })

  it('changes the tier with no confirmation at all', async () => {
    // The asymmetry is the point: a tier moves a quota, not a privilege, and
    // revokes nothing. Confirming it too would teach the operator to click
    // through the dialogs that do matter.
    const { user, mutate } = setupRow()

    await user.click(screen.getByRole('button', { name: 'free' }))
    await user.click(await screen.findByRole('menuitemradio', { name: 'pro' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(mutate).toHaveBeenCalledWith({ userId: 'u1', data: { tier: 'pro' } }, expect.anything())
  })
})
