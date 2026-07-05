import { useState } from 'react'
import { Card } from '../ui'
import {
  useCalendarStatus,
  useConnectCalendar,
  useDisconnectCalendar,
  useSyncCalendar,
} from '../../hooks/useCalendar'
import type { CalendarSyncInfo } from '../../types'

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || ''

function formatLastSynced(iso: string | null): string {
  if (!iso) return 'Never'
  const d = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return 'Just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  return d.toLocaleDateString()
}

function ConnectedCalendar({ cal }: { cal: CalendarSyncInfo }) {
  const disconnectMutation = useDisconnectCalendar()
  const syncMutation = useSyncCalendar()
  const [confirming, setConfirming] = useState(false)

  return (
    <div className="flex items-center justify-between gap-4 rounded-lg border border-border p-3">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <svg className="h-5 w-5 flex-shrink-0 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
          <span className="text-sm font-medium text-text truncate">
            {cal.google_calendar_id}
          </span>
        </div>
        <div className="mt-1 flex items-center gap-3 text-xs text-text-muted">
          <span className="capitalize">{cal.sync_direction}</span>
          <span>{cal.event_count} events</span>
          <span>Synced: {formatLastSynced(cal.last_synced_at)}</span>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={() => syncMutation.mutate()}
          disabled={syncMutation.isPending}
          className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-text hover:bg-surface-alt disabled:opacity-50 transition-colors"
        >
          {syncMutation.isPending ? 'Syncing...' : 'Sync Now'}
        </button>
        {confirming ? (
          <div className="flex items-center gap-1">
            <button
              onClick={() => {
                disconnectMutation.mutate(cal.id)
                setConfirming(false)
              }}
              disabled={disconnectMutation.isPending}
              className="rounded-lg bg-red px-3 py-1.5 text-xs font-medium text-on-accent hover:opacity-90 disabled:opacity-50 transition-colors"
            >
              Confirm
            </button>
            <button
              onClick={() => setConfirming(false)}
              className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-text hover:bg-surface-alt transition-colors"
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            onClick={() => setConfirming(true)}
            className="rounded-lg border border-red/30 px-3 py-1.5 text-xs font-medium text-red-fg hover:bg-red-soft transition-colors"
          >
            Disconnect
          </button>
        )}
      </div>
    </div>
  )
}

export function CalendarSyncSection() {
  const { data, isLoading } = useCalendarStatus()
  const connectMutation = useConnectCalendar()

  const calendars = data?.calendars ?? []

  const handleConnect = () => {
    if (!GOOGLE_CLIENT_ID) {
      return
    }

    // Open Google OAuth consent in a popup
    const redirectUri = `${window.location.origin}/api/auth/oauth/google/callback`
    const scope = 'https://www.googleapis.com/auth/calendar'
    const authUrl =
      `https://accounts.google.com/o/oauth2/v2/auth?` +
      `client_id=${encodeURIComponent(GOOGLE_CLIENT_ID)}` +
      `&redirect_uri=${encodeURIComponent(redirectUri)}` +
      `&response_type=code` +
      `&scope=${encodeURIComponent(scope)}` +
      `&access_type=offline` +
      `&prompt=consent`

    const popup = window.open(authUrl, 'google-calendar-auth', 'width=600,height=700')

    // Listen for the auth code from the popup
    const handleMessage = (event: MessageEvent) => {
      if (event.origin !== window.location.origin) return
      if (event.data?.type === 'google-calendar-auth' && event.data?.code) {
        connectMutation.mutate(event.data.code)
        popup?.close()
        window.removeEventListener('message', handleMessage)
      }
    }
    window.addEventListener('message', handleMessage)
  }

  if (isLoading) {
    return (
      <Card>
        <h2 className="text-lg font-semibold text-text mb-4">Google Calendar</h2>
        <div className="animate-pulse space-y-3">
          <div className="h-4 bg-surface-alt rounded w-3/4" />
          <div className="h-4 bg-surface-alt rounded w-1/2" />
        </div>
      </Card>
    )
  }

  return (
    <Card>
      <h2 className="text-lg font-semibold text-text mb-1">Google Calendar</h2>
      <p className="text-sm text-text-muted mb-4">
        Sync your deadlines and exams with Google Calendar.
      </p>

      {calendars.length > 0 ? (
        <div className="space-y-3">
          {calendars.map((cal) => (
            <ConnectedCalendar key={cal.id} cal={cal} />
          ))}
        </div>
      ) : (
        <div className="text-center py-4">
          <svg
            className="mx-auto h-10 w-10 text-text-muted mb-3"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
          </svg>
          <p className="text-sm text-text-muted mb-3">
            Connect your Google Calendar to automatically sync study deadlines and exam dates.
          </p>
          <button
            onClick={handleConnect}
            disabled={connectMutation.isPending || !GOOGLE_CLIENT_ID}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" />
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
            </svg>
            {connectMutation.isPending ? 'Connecting...' : 'Connect Google Calendar'}
          </button>
          {!GOOGLE_CLIENT_ID && (
            <p className="mt-2 text-xs text-text-muted">
              Set VITE_GOOGLE_CLIENT_ID to enable Google Calendar integration.
            </p>
          )}
        </div>
      )}

      {connectMutation.isError && (
        <p className="mt-3 text-sm text-red-fg">
          Failed to connect: {connectMutation.error instanceof Error ? connectMutation.error.message : 'Unknown error'}
        </p>
      )}
    </Card>
  )
}
