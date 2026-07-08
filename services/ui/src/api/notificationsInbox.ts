import { api } from './client'
import type { InboxNotification, MarkReadResponse, UnreadCountResponse } from '../types'

export const notificationsInboxApi = {
  /** GET /api/notifications — newest first; unreadOnly filters to unread. */
  list: (unreadOnly = false, limit = 50) =>
    api.get<InboxNotification[]>(`/notifications?unread=${unreadOnly}&limit=${limit}`),

  /** GET /api/notifications/unread-count */
  unreadCount: () => api.get<UnreadCountResponse>('/notifications/unread-count'),

  /** POST /api/notifications/mark-read — idempotent. */
  markRead: (ids: string[]) =>
    api.post<MarkReadResponse>('/notifications/mark-read', { ids }),
}
