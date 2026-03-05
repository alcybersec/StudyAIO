import { Card } from '../ui'
import {
  useNotificationPreferences,
  useUpdatePreferences,
  useTestNotification,
} from '../../hooks/useNotifications'
import { TelegramLinkCard } from './TelegramLinkCard'
import type { NotificationPreferenceItem } from '../../types'

const EVENT_LABELS: Record<string, string> = {
  pipeline_complete: 'File Processed',
  review_created: 'Review Created',
  cards_due: 'Cards Due',
  exam_reminder: 'Exam Reminder',
  weekly_digest: 'Weekly Digest',
}

const EVENT_DESCRIPTIONS: Record<string, string> = {
  pipeline_complete: 'When a file finishes processing',
  review_created: 'When a review item needs attention',
  cards_due: 'Daily reminder for due flashcards',
  exam_reminder: 'Upcoming exam alerts',
  weekly_digest: 'Weekly study summary',
}

const CHANNELS = ['email', 'telegram'] as const
const EVENT_TYPES = ['pipeline_complete', 'review_created', 'cards_due', 'exam_reminder', 'weekly_digest'] as const

export function NotificationsSection() {
  const { data, isLoading } = useNotificationPreferences()
  const updateMutation = useUpdatePreferences()
  const testMutation = useTestNotification()

  const preferences = data?.preferences ?? []

  const isEnabled = (channel: string, eventType: string): boolean => {
    const pref = preferences.find(
      (p) => p.channel === channel && p.event_type === eventType
    )
    return pref?.enabled ?? false
  }

  const handleToggle = (channel: string, eventType: string) => {
    const currentlyEnabled = isEnabled(channel, eventType)
    const updated: NotificationPreferenceItem[] = preferences.map((p) => {
      if (p.channel === channel && p.event_type === eventType) {
        return { ...p, enabled: !currentlyEnabled }
      }
      return p
    })

    // Add if not in list yet
    const exists = updated.some(
      (p) => p.channel === channel && p.event_type === eventType
    )
    if (!exists) {
      updated.push({
        channel,
        event_type: eventType,
        enabled: !currentlyEnabled,
      })
    }

    updateMutation.mutate(updated)
  }

  const handleTest = (channel: string) => {
    testMutation.mutate(channel)
  }

  // Derive telegram link status from preferences data
  const telegramPrefs = preferences.filter((p) => p.channel === 'telegram')
  const hasTelegramEnabled = telegramPrefs.some((p) => p.enabled)

  if (isLoading) {
    return (
      <Card>
        <h2 className="text-lg font-semibold text-text mb-4">Notifications</h2>
        <div className="animate-pulse space-y-3">
          <div className="h-4 bg-surface-alt rounded w-3/4" />
          <div className="h-4 bg-surface-alt rounded w-1/2" />
        </div>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      <Card>
        <h2 className="text-lg font-semibold text-text mb-1">Notifications</h2>
        <p className="text-sm text-text-muted mb-4">
          Choose which events you want to be notified about and how.
        </p>

        {/* Preference grid */}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-2 pr-4 font-medium text-text-muted">Event</th>
                {CHANNELS.map((ch) => (
                  <th key={ch} className="text-center py-2 px-3 font-medium text-text-muted capitalize">
                    {ch}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {EVENT_TYPES.map((event) => (
                <tr key={event} className="border-b border-border/50">
                  <td className="py-3 pr-4">
                    <div className="font-medium text-text">{EVENT_LABELS[event]}</div>
                    <div className="text-xs text-text-muted">{EVENT_DESCRIPTIONS[event]}</div>
                  </td>
                  {CHANNELS.map((ch) => (
                    <td key={ch} className="text-center py-3 px-3">
                      <button
                        onClick={() => handleToggle(ch, event)}
                        disabled={updateMutation.isPending}
                        className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary/20 ${
                          isEnabled(ch, event)
                            ? 'bg-primary'
                            : 'bg-border'
                        }`}
                        role="switch"
                        aria-checked={isEnabled(ch, event)}
                        aria-label={`${EVENT_LABELS[event]} via ${ch}`}
                      >
                        <span
                          className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                            isEnabled(ch, event) ? 'translate-x-[18px]' : 'translate-x-[3px]'
                          }`}
                        />
                      </button>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Test buttons */}
        <div className="mt-4 flex items-center gap-3">
          <span className="text-sm text-text-muted">Send test:</span>
          {CHANNELS.map((ch) => (
            <button
              key={ch}
              onClick={() => handleTest(ch)}
              disabled={testMutation.isPending}
              className="px-3 py-1.5 text-xs font-medium text-text bg-surface-alt border border-border rounded-lg hover:bg-border disabled:opacity-50 transition-colors capitalize"
            >
              {ch}
            </button>
          ))}
          {testMutation.isSuccess && (
            <span className="text-xs text-green-600 dark:text-green-400">
              {testMutation.data.message}
            </span>
          )}
          {testMutation.isError && (
            <span className="text-xs text-red-600 dark:text-red-400">
              {testMutation.error instanceof Error ? testMutation.error.message : 'Failed'}
            </span>
          )}
        </div>
      </Card>

      {/* Telegram linking */}
      <TelegramLinkCard linked={hasTelegramEnabled} />
    </div>
  )
}
