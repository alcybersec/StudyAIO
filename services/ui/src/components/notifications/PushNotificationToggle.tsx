import { usePushNotifications } from '../../hooks/usePushNotifications'

export function PushNotificationToggle() {
  const { permission, subscribed, loading, subscribe, unsubscribe } = usePushNotifications()

  if (permission === 'unsupported') {
    return (
      <div className="text-sm text-text-muted">
        Push notifications are not supported in this browser.
      </div>
    )
  }

  if (permission === 'denied') {
    return (
      <div className="text-sm text-text-muted">
        Push notifications are blocked. Enable them in your browser settings to receive alerts.
      </div>
    )
  }

  return (
    <div className="flex items-center justify-between">
      <div>
        <div className="text-sm font-medium text-text">Push Notifications</div>
        <div className="text-xs text-text-muted">
          {subscribed ? 'Receiving browser push notifications' : 'Get notified in your browser'}
        </div>
      </div>
      <button
        onClick={subscribed ? unsubscribe : subscribe}
        disabled={loading}
        className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors disabled:opacity-50 ${
          subscribed
            ? 'bg-surface-alt text-text hover:bg-red-soft hover:text-red-fg'
            : 'bg-primary text-white hover:bg-primary/90'
        }`}
      >
        {loading ? 'Working...' : subscribed ? 'Disable' : 'Enable'}
      </button>
    </div>
  )
}
