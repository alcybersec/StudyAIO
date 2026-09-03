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

  it('toggling the status badge sends an is_active update', async () => {
    const user = userEvent.setup()
    const mutate = vi.fn()
    mockUpdate.mockReturnValue(asResult({ mutate, isPending: false }))
    mockMetrics.mockReturnValue(asResult({ data: metricsData, isLoading: false, isError: false, refetch: vi.fn() }))
    mockUsers.mockReturnValue(
      asResult({
        data: { users: [sampleUser], total: 1, offset: 0, limit: 25 },
        isLoading: false,
        isError: false,
        refetch: vi.fn(),
      }),
    )

    renderPage()
    await user.click(screen.getByRole('button', { name: /deactivate user/i }))

    expect(mutate).toHaveBeenCalledWith({ userId: 'u1', data: { is_active: false } })
  })
})
