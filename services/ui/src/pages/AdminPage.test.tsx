import { MemoryRouter } from 'react-router-dom'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AdminPage } from './AdminPage'
import { useAdminUsers, useSystemMetrics, useUpdateAdminUser } from '../hooks/useApi'

vi.mock('../hooks/useApi', async (importOriginal) => {
  // Stubs are DERIVED from the real module's exports rather than listed by
  // hand. A hand-written factory replaces the whole module, so any hook a child
  // component starts calling is `undefined` at call time and every test in this
  // file fails on a React render error that points at the mock instead of the
  // cause. That happened three times while building email invites alone
  // (useSendInvite, useResendInvite, and once before that) — each time costing
  // a debugging round-trip on 14 unrelated failures.
  //
  // Only exports named `use*` are stubbed; anything else (query-key helpers,
  // constants) keeps its real value.
  const actual = await importOriginal<typeof import('../hooks/useApi')>()

  // One shape serving both hook kinds: queries read data/isLoading/isError/
  // refetch, mutations read mutate/isPending. A hook this file does not drive
  // only has to render without throwing.
  const inert = () => ({
    data: undefined,
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    isPending: false,
  })

  const stubs = Object.fromEntries(
    Object.keys(actual)
      .filter((name) => name.startsWith('use'))
      .map((name) => [name, vi.fn(inert)]),
  )

  return {
    ...actual,
    ...stubs,
    // The three this file actually drives. Left bare so beforeEach must set
    // them — a test that forgets fails loudly rather than reading an inert stub.
    useAdminUsers: vi.fn(),
    useSystemMetrics: vi.fn(),
    useUpdateAdminUser: vi.fn(),
  }
})

const toastSuccess = vi.fn()
const toastError = vi.fn()
vi.mock('sonner', () => ({
  toast: {
    success: (...args: unknown[]) => toastSuccess(...args),
    error: (...args: unknown[]) => toastError(...args),
    message: (...args: unknown[]) => toastSuccess(...args),
  },
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
  mfa_enabled: false,
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

describe('useApi mock coverage', () => {
  it('stubs every hook the real module exports', async () => {
    // The guard for the failure this mock was rewritten to end. A hand-listed
    // factory silently omits any hook added later, and the omission surfaces as
    // 14 unrelated render errors pointing at the mock rather than the cause.
    //
    // Deriving the stubs makes that structurally impossible; this asserts it
    // stays that way, including if someone reverts to listing them by hand.
    const actual = await vi.importActual<typeof import('../hooks/useApi')>('../hooks/useApi')
    const mocked = (await import('../hooks/useApi')) as unknown as Record<string, unknown>

    // vi.isMockFunction, NOT typeof === 'function'. The factory spreads the
    // real module first, so an un-stubbed hook falls through to the genuine
    // implementation — still a function, and it would call useQuery with no
    // provider and throw at render. A typeof check passes in exactly the case
    // this test exists to catch; it was written that way first and verified
    // useless by reverting the factory and watching it stay green.
    const notStubbed = Object.keys(actual)
      .filter((name) => name.startsWith('use'))
      .filter((name) => !vi.isMockFunction(mocked[name]))

    expect(notStubbed).toEqual([])
  })
})

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

// ── The toast reports the server's answer ──────────────────────
//
// GL#3. `sessions_revoked` comes back on the PATCH, so the success line states
// what happened rather than what was asked for. The distinction bites when the
// row the page holds is stale: the user already had that role, the server
// revokes nothing, and the old code still announced a sign-out.
describe('AdminPage success toasts', () => {
  function confirmRoleChangeWith(sessionsRevoked: boolean) {
    const mutate = vi.fn((_vars, opts) =>
      opts.onSuccess({ ...sampleUser, role: 'admin', sessions_revoked: sessionsRevoked }),
    )
    mockUpdate.mockReturnValue(asResult({ mutate, isPending: false }))
    mockMetrics.mockReturnValue(
      asResult({ data: metricsData, isLoading: false, isError: false, refetch: vi.fn() }),
    )
    mockUsers.mockReturnValue(
      asResult({
        data: { users: [sampleUser], total: 1, offset: 0, limit: 25 },
        isLoading: false,
        isError: false,
        refetch: vi.fn(),
      }),
    )
    renderPage()
    return userEvent.setup()
  }

  it('says the user was signed out when the server revoked their sessions', async () => {
    const user = await confirmRoleChangeWith(true)
    await pickRole(user, 'user', 'admin')
    await user.click(screen.getByRole('button', { name: /change role to admin/i }))

    expect(toastSuccess).toHaveBeenCalledWith(expect.stringContaining('signed out on every device'))
  })

  it('does not claim a sign-out the server did not perform', async () => {
    const user = await confirmRoleChangeWith(false)
    await pickRole(user, 'user', 'admin')
    await user.click(screen.getByRole('button', { name: /change role to admin/i }))

    expect(toastSuccess).toHaveBeenCalledWith(expect.stringContaining('No sessions needed revoking'))
    expect(toastSuccess).not.toHaveBeenCalledWith(expect.stringContaining('signed out'))
  })
})
