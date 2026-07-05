import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { Bell, CalendarClock, FileCheck, Inbox, Zap } from 'lucide-react'
import { notificationsInboxApi } from '../../api/notificationsInbox'
import type { InboxNotification } from '../../types'
import { notificationIcon } from '../../lib/notificationDisplay'
import { NotificationCenter } from './NotificationCenter'

vi.mock('../../api/notificationsInbox', () => ({
  notificationsInboxApi: {
    list: vi.fn(),
    unreadCount: vi.fn(),
    markRead: vi.fn(),
  },
}))

const mockedApi = vi.mocked(notificationsInboxApi)

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => mockNavigate }
})

function makeNotification(overrides: Partial<InboxNotification> = {}): InboxNotification {
  return {
    id: 'n1',
    kind: 'pipeline',
    title: 'CSIT302 week 9 processed',
    body: null,
    href: '/courses/CSIT302/weeks/9',
    read_at: null,
    created_at: new Date().toISOString(),
    ...overrides,
  }
}

function renderCenter(onNavigate?: () => void) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  )
  return render(<NotificationCenter onNavigate={onNavigate} />, { wrapper })
}

describe('notificationIcon', () => {
  it('maps each kind to its icon and falls back to the bell', () => {
    expect(notificationIcon('pipeline')).toBe(FileCheck)
    expect(notificationIcon('review')).toBe(Inbox)
    expect(notificationIcon('achievement')).toBe(Zap)
    expect(notificationIcon('deadline')).toBe(CalendarClock)
    expect(notificationIcon('unknown')).toBe(Bell)
  })
})

describe('NotificationCenter', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows skeleton rows while loading', () => {
    mockedApi.list.mockReturnValue(new Promise(() => {}))
    renderCenter()
    expect(screen.getByLabelText('Loading notifications')).toBeInTheDocument()
  })

  it('shows the empty state when there are no notifications', async () => {
    mockedApi.list.mockResolvedValue([])
    renderCenter()
    expect(await screen.findByText(/all caught up/i)).toBeInTheDocument()
  })

  it('shows a compact error state when the list fails with no cache', async () => {
    mockedApi.list.mockRejectedValue(new Error('boom'))
    renderCenter()
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.getByText(/notifications couldn't load/i)).toBeInTheDocument()
  })

  it('renders notifications with unread dot and relative time', async () => {
    mockedApi.list.mockResolvedValue([
      makeNotification(),
      makeNotification({ id: 'n2', kind: 'achievement', title: 'Level up!', read_at: new Date().toISOString() }),
    ])
    renderCenter()
    expect(await screen.findByText('CSIT302 week 9 processed')).toBeInTheDocument()
    expect(screen.getByText('Level up!')).toBeInTheDocument()
    expect(screen.getAllByLabelText('unread')).toHaveLength(1)
    expect(screen.getAllByText('just now')).toHaveLength(2)
  })

  it('marks read and navigates via href on click', async () => {
    const user = userEvent.setup()
    mockedApi.list.mockResolvedValue([makeNotification()])
    mockedApi.markRead.mockResolvedValue({ updated: 1 })
    const onNavigate = vi.fn()
    renderCenter(onNavigate)

    await user.click(await screen.findByText('CSIT302 week 9 processed'))
    expect(mockedApi.markRead).toHaveBeenCalledWith(['n1'])
    expect(mockNavigate).toHaveBeenCalledWith('/courses/CSIT302/weeks/9')
    expect(onNavigate).toHaveBeenCalled()
  })

  it('marks all unread read via the header action', async () => {
    const user = userEvent.setup()
    mockedApi.list.mockResolvedValue([
      makeNotification({ id: 'a' }),
      makeNotification({ id: 'b', read_at: new Date().toISOString() }),
      makeNotification({ id: 'c' }),
    ])
    mockedApi.markRead.mockResolvedValue({ updated: 2 })
    renderCenter()

    await screen.findAllByText('CSIT302 week 9 processed')
    await user.click(screen.getByRole('button', { name: /mark all read/i }))
    await waitFor(() => expect(mockedApi.markRead).toHaveBeenCalledWith(['a', 'c']))
  })

  it('disables mark all read when nothing is unread', async () => {
    mockedApi.list.mockResolvedValue([makeNotification({ read_at: new Date().toISOString() })])
    renderCenter()
    await screen.findByText('CSIT302 week 9 processed')
    expect(screen.getByRole('button', { name: /mark all read/i })).toBeDisabled()
  })
})
