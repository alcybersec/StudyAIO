import { usePushNotifications } from '../../hooks/usePushNotifications'
import { useTranslation } from 'react-i18next'

export function PushNotificationToggle() {
  const { t } = useTranslation()

  const { permission, subscribed, loading, subscribe, unsubscribe } = usePushNotifications()

  if (permission === 'unsupported') {
    return (
      <div className="text-sm text-text-muted">
        {t('Push notifications are not supported in this browser.')}
      </div>
    )
  }

  if (permission === 'denied') {
    return (
      <div className="text-sm text-text-muted">
        {t('Push notifications are blocked. Enable them in your browser settings to receive alerts.')}
      </div>
    )
  }

  return (
    <div className="flex items-center justify-between">
      <div>
        <div className="text-sm font-medium text-text">{t('Push Notifications')}</div>
        <div className="text-xs text-text-muted">
          {subscribed ? 'Receiving browser push notifications' : 'Get notified in your browser'}
        </div>
      </div>
      <button
        onClick={subscribed ? unsubscribe : subscribe}
        disabled={loading}
        className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors disabled:opacity-50 ${
          subscribed
            ? 'bg-surface-0 text-text hover:bg-red-soft hover:text-red-fg'
            : 'bg-sage text-on-accent hover:bg-sage-hover'
        }`}
      >
        {loading ? 'Working...' : subscribed ? 'Disable' : 'Enable'}
      </button>
    </div>
  )
}
