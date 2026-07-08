import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { MobileNav } from './MobileNav'

const mockUseAuth = vi.fn()
const mockUseDashboard = vi.fn()
const mockUseCourses = vi.fn()
const mockUseUnreadCount = vi.fn()

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}))
vi.mock('../../hooks/useApi', () => ({
  useDashboard: () => mockUseDashboard(),
  useCourses: () => mockUseCourses(),
}))
vi.mock('../../hooks/useNotificationInbox', () => ({
  useUnreadCount: () => mockUseUnreadCount(),
  useNotifications: () => ({ data: [], isLoading: false, isError: false, refetch: vi.fn() }),
  useMarkNotificationsRead: () => ({ mutate: vi.fn(), isPending: false }),
}))

function setup({ role = 'user', unread = 0 }: { role?: string; unread?: number } = {}) {
  mockUseAuth.mockReturnValue({
    user: { id: 'u1', username: 'alex', role, tier: 'free', avatar_url: null },
    isSelfHosted: true,
    isDemo: false,
    logout: vi.fn(),
  })
  mockUseUnreadCount.mockReturnValue({ data: unread })
  mockUseDashboard.mockReturnValue({ data: { pending_review_count: 2 } })
  mockUseCourses.mockReturnValue({
    data: [{ id: 'c1', code: 'CSIT302', name: 'Cybersecurity', weeks_covered: 9 }],
  })
  return render(
    <MemoryRouter>
      <MobileNav />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('MobileNav', () => {
  it('renders the five bottom tabs', () => {
    setup()
    const nav = screen.getByRole('navigation')
    expect(within(nav).getByRole('link', { name: /home/i })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: /study/i })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: /ask/i })).toHaveAttribute('href', '/ask')
    expect(within(nav).getByRole('button', { name: /library/i })).toBeInTheDocument()
    expect(within(nav).getByRole('button', { name: /more/i })).toBeInTheDocument()
  })

  it('opens the Library sheet listing courses', async () => {
    const u = userEvent.setup()
    setup()
    await u.click(screen.getByRole('button', { name: /library/i }))
    expect(await screen.findByRole('link', { name: /CSIT302/ })).toHaveAttribute(
      'href',
      '/courses/CSIT302',
    )
    // Upload lives in Library too
    expect(screen.getByRole('link', { name: /upload/i })).toBeInTheDocument()
  })

  it('opens the More sheet with secondary destinations', async () => {
    const u = userEvent.setup()
    setup()
    await u.click(screen.getByRole('button', { name: /more/i }))
    expect(await screen.findByRole('link', { name: /review/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /analytics/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /achievements/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /settings/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /profile/i })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /admin/i })).not.toBeInTheDocument()
  })

  it('includes Admin in the More sheet for admins', async () => {
    const u = userEvent.setup()
    setup({ role: 'admin' })
    await u.click(screen.getByRole('button', { name: /more/i }))
    expect(await screen.findByRole('link', { name: /admin/i })).toBeInTheDocument()
  })

  it('opens the notification center from the More sheet', async () => {
    const u = userEvent.setup()
    setup()
    await u.click(screen.getByRole('button', { name: /more/i }))
    await u.click(await screen.findByRole('button', { name: /notifications/i }))
    expect(await screen.findByText(/you're all caught up/i)).toBeInTheDocument()
  })

  it('shows the capped unread badge on the notifications entry', async () => {
    const u = userEvent.setup()
    setup({ unread: 11 })
    await u.click(screen.getByRole('button', { name: /more/i }))
    const entry = await screen.findByRole('button', { name: /notifications/i })
    expect(entry).toHaveTextContent('9+')
  })
})
