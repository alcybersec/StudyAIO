import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { notificationsInboxApi } from '../api/notificationsInbox'
import type { InboxNotification, UnreadCountResponse } from '../types'

/** Shared cache namespace for the notification inbox. */
export const NOTIFICATION_INBOX_KEY = ['notifications', 'inbox'] as const

export function useNotifications(unreadOnly = false) {
  return useQuery({
    queryKey: [...NOTIFICATION_INBOX_KEY, 'list', unreadOnly],
    queryFn: () => notificationsInboxApi.list(unreadOnly),
  })
}

export function useUnreadCount() {
  return useQuery({
    queryKey: [...NOTIFICATION_INBOX_KEY, 'unread-count'],
    queryFn: notificationsInboxApi.unreadCount,
    refetchInterval: 60_000,
    select: (data) => data.count,
  })
}

/**
 * Mark notifications read with an optimistic update: `read_at` is set locally
 * on the cached lists and the unread count drops immediately; the server
 * result reconciles on settle.
 */
export function useMarkNotificationsRead() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (ids: string[]) => notificationsInboxApi.markRead(ids),
    onMutate: async (ids) => {
      await queryClient.cancelQueries({ queryKey: NOTIFICATION_INBOX_KEY })
      const previous = queryClient.getQueriesData({ queryKey: NOTIFICATION_INBOX_KEY })

      const idSet = new Set(ids)
      const now = new Date().toISOString()
      queryClient.setQueriesData<InboxNotification[]>(
        { queryKey: [...NOTIFICATION_INBOX_KEY, 'list'] },
        (old) => old?.map((n) => (idSet.has(n.id) && !n.read_at ? { ...n, read_at: now } : n)),
      )
      queryClient.setQueryData<UnreadCountResponse>(
        [...NOTIFICATION_INBOX_KEY, 'unread-count'],
        (old) => (old ? { count: Math.max(0, old.count - ids.length) } : old),
      )
      return { previous }
    },
    onError: (_err, _ids, context) => {
      for (const [key, data] of context?.previous ?? []) {
        queryClient.setQueryData(key, data)
      }
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: NOTIFICATION_INBOX_KEY }),
  })
}
