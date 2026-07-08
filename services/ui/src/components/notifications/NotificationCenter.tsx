import { useNavigate } from 'react-router-dom'
import { useMarkNotificationsRead, useNotifications } from '../../hooks/useNotificationInbox'
import { notificationIcon, relativeTime } from '../../lib/notificationDisplay'
import type { InboxNotification } from '../../types'
import { ErrorState } from '../ui/ErrorState'
import { Skeleton } from '../ui/Skeleton'

interface NotificationCenterProps {
  /** Called after a notification navigates, so the containing panel can close. */
  onNavigate?: () => void
}

export function NotificationCenter({ onNavigate }: NotificationCenterProps) {
  const navigate = useNavigate()
  const { data: notifications, isLoading, isError, refetch } = useNotifications()
  const markRead = useMarkNotificationsRead()

  const unreadIds = (notifications ?? []).filter((n) => !n.read_at).map((n) => n.id)

  const handleClick = (notification: InboxNotification) => {
    if (!notification.read_at) {
      markRead.mutate([notification.id])
    }
    if (notification.href) {
      navigate(notification.href)
      onNavigate?.()
    }
  }

  return (
    <div className="flex flex-col">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <span className="text-sm font-semibold text-text">Notifications</span>
        <button
          type="button"
          onClick={() => markRead.mutate(unreadIds)}
          disabled={unreadIds.length === 0 || markRead.isPending}
          className="text-[11px] text-text-faint hover:text-text-muted disabled:opacity-50 disabled:cursor-default cursor-pointer transition-colors"
        >
          mark all read
        </button>
      </div>

      {/* Cached data wins over a background error — offline still shows the inbox. */}
      {isLoading ? (
        <div className="px-4 py-3 space-y-3" aria-label="Loading notifications">
          {[0, 1, 2].map((i) => (
            <div key={i} className="flex gap-3">
              <Skeleton width={14} height={14} rounded />
              <div className="flex-1 space-y-1.5">
                <Skeleton height={13} width="85%" />
                <Skeleton height={10} width={56} />
              </div>
            </div>
          ))}
        </div>
      ) : notifications ? (
        notifications.length === 0 ? (
          <p className="px-4 py-8 text-center text-sm text-text-muted">
            You&apos;re all caught up.
          </p>
        ) : (
          <ul className="divide-y divide-border max-h-80 overflow-y-auto">
            {notifications.map((n) => {
              const Icon = notificationIcon(n.kind)
              const unread = !n.read_at
              return (
                <li key={n.id} className={unread ? '' : 'opacity-55'}>
                  <button
                    type="button"
                    onClick={() => handleClick(n)}
                    className="w-full flex gap-3 px-4 py-3 text-left hover:bg-surface-2 cursor-pointer transition-colors"
                  >
                    <span className={`mt-0.5 shrink-0 ${unread ? 'text-sage-fg' : 'text-text-faint'}`}>
                      <Icon size={14} aria-hidden />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-[13px] leading-snug text-text">{n.title}</span>
                      {n.body && (
                        <span className="block text-[11px] text-text-muted mt-0.5 truncate">
                          {n.body}
                        </span>
                      )}
                      <span className="block text-[10px] font-mono text-text-faint mt-1">
                        {relativeTime(n.created_at)}
                      </span>
                    </span>
                    {unread && (
                      <span
                        className="ml-auto mt-1.5 w-1.5 h-1.5 rounded-full bg-amber shrink-0"
                        aria-label="unread"
                      />
                    )}
                  </button>
                </li>
              )
            })}
          </ul>
        )
      ) : isError ? (
        <div className="p-4">
          <ErrorState compact title="Notifications couldn't load" onRetry={() => refetch()} />
        </div>
      ) : null}

      <div className="px-4 py-2.5 border-t border-border text-[10px] font-mono text-text-faint">
        pipeline · review · achievements · deadlines — all in one place
      </div>
    </div>
  )
}
