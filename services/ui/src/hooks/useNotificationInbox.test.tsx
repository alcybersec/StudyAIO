import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { notificationsInboxApi } from '../api/notificationsInbox'
import type { InboxNotification } from '../types'
import {
  NOTIFICATION_INBOX_KEY,
  useMarkNotificationsRead,
  useNotifications,
  useUnreadCount,
} from './useNotificationInbox'

vi.mock('../api/notificationsInbox', () => ({
  notificationsInboxApi: {
    list: vi.fn(),
    unreadCount: vi.fn(),
    markRead: vi.fn(),
  },
}))

const mockedApi = vi.mocked(notificationsInboxApi)

function makeNotification(overrides: Partial<InboxNotification> = {}): InboxNotification {
  return {
    id: 'n1',
    kind: 'pipeline',
    title: 'CSIT302 week 9 processed',
    body: null,
    href: '/courses/CSIT302/weeks/9',
    read_at: null,
    created_at: '2026-07-04T10:00:00',
    ...overrides,
  }
}

function createWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  return { client, wrapper }
}

describe('useNotifications', () => {
  beforeEach(() => vi.clearAllMocks())

  it('fetches the inbox list', async () => {
    mockedApi.list.mockResolvedValue([makeNotification()])
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useNotifications(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(mockedApi.list).toHaveBeenCalledWith(false)
    expect(result.current.data).toHaveLength(1)
  })
})

describe('useUnreadCount', () => {
  beforeEach(() => vi.clearAllMocks())

  it('selects the numeric count from the response', async () => {
    mockedApi.unreadCount.mockResolvedValue({ count: 3 })
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useUnreadCount(), { wrapper })
    await waitFor(() => expect(result.current.data).toBe(3))
  })
})

describe('useMarkNotificationsRead', () => {
  beforeEach(() => vi.clearAllMocks())

  it('optimistically sets read_at on cached lists and drops the unread count', async () => {
    // Never-resolving mutation keeps the optimistic state observable.
    mockedApi.markRead.mockReturnValue(new Promise(() => {}))
    const { client, wrapper } = createWrapper()
    const unread = makeNotification({ id: 'a' })
    const other = makeNotification({ id: 'b' })
    client.setQueryData([...NOTIFICATION_INBOX_KEY, 'list', false], [unread, other])
    client.setQueryData([...NOTIFICATION_INBOX_KEY, 'unread-count'], { count: 2 })

    const { result } = renderHook(() => useMarkNotificationsRead(), { wrapper })
    act(() => {
      result.current.mutate(['a'])
    })

    await waitFor(() => {
      const list = client.getQueryData<InboxNotification[]>([
        ...NOTIFICATION_INBOX_KEY,
        'list',
        false,
      ])
      expect(list?.find((n) => n.id === 'a')?.read_at).not.toBeNull()
    })
    const list = client.getQueryData<InboxNotification[]>([...NOTIFICATION_INBOX_KEY, 'list', false])
    expect(list?.find((n) => n.id === 'b')?.read_at).toBeNull()
    expect(client.getQueryData([...NOTIFICATION_INBOX_KEY, 'unread-count'])).toEqual({ count: 1 })
  })

  it('rolls back the optimistic update when the request fails', async () => {
    mockedApi.markRead.mockRejectedValue(new Error('boom'))
    const { client, wrapper } = createWrapper()
    const unread = makeNotification({ id: 'a' })
    client.setQueryData([...NOTIFICATION_INBOX_KEY, 'list', false], [unread])
    client.setQueryData([...NOTIFICATION_INBOX_KEY, 'unread-count'], { count: 1 })

    const { result } = renderHook(() => useMarkNotificationsRead(), { wrapper })
    act(() => {
      result.current.mutate(['a'])
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
    const list = client.getQueryData<InboxNotification[]>([...NOTIFICATION_INBOX_KEY, 'list', false])
    expect(list?.[0].read_at).toBeNull()
    expect(client.getQueryData([...NOTIFICATION_INBOX_KEY, 'unread-count'])).toEqual({ count: 1 })
  })
})
