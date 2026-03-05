import { useState } from 'react'
import { Card } from '../ui'
import { useTelegramLink, useUnlinkTelegram } from '../../hooks/useNotifications'

interface TelegramLinkCardProps {
  linked: boolean
  username?: string | null
}

export function TelegramLinkCard({ linked, username }: TelegramLinkCardProps) {
  const linkMutation = useTelegramLink()
  const unlinkMutation = useUnlinkTelegram()
  const [deepLink, setDeepLink] = useState<string | null>(null)

  const handleLink = async () => {
    try {
      const result = await linkMutation.mutateAsync()
      setDeepLink(result.deep_link)
    } catch {
      // Error handled by mutation state
    }
  }

  const handleUnlink = async () => {
    try {
      await unlinkMutation.mutateAsync()
      setDeepLink(null)
    } catch {
      // Error handled by mutation state
    }
  }

  return (
    <Card>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-text">Telegram</h3>
        {linked ? (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400">
            Connected{username ? ` (@${username})` : ''}
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-surface-alt text-text-muted">
            Not connected
          </span>
        )}
      </div>

      {linked ? (
        <div className="space-y-3">
          <p className="text-sm text-text-muted">
            Your Telegram account is linked. You'll receive notifications via the StudyAIO bot.
          </p>
          <button
            onClick={handleUnlink}
            disabled={unlinkMutation.isPending}
            className="px-3 py-1.5 text-sm font-medium text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/50 border border-red-200 dark:border-red-900 rounded-lg hover:bg-red-100 dark:hover:bg-red-950 disabled:opacity-50 transition-colors"
          >
            {unlinkMutation.isPending ? 'Unlinking...' : 'Unlink Telegram'}
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-text-muted">
            Link your Telegram account to receive notifications via the StudyAIO bot.
          </p>

          {deepLink ? (
            <div className="space-y-2">
              <p className="text-sm text-text">Click the link below to connect in Telegram:</p>
              <a
                href={deepLink}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-4 py-2 bg-[#0088cc] text-white text-sm font-medium rounded-lg hover:bg-[#006da3] transition-colors"
              >
                Open in Telegram
              </a>
              <p className="text-xs text-text-muted">
                After clicking, press Start in the Telegram bot to complete the link.
              </p>
            </div>
          ) : (
            <button
              onClick={handleLink}
              disabled={linkMutation.isPending}
              className="px-3 py-1.5 text-sm font-medium text-primary bg-primary/10 border border-primary/20 rounded-lg hover:bg-primary/20 disabled:opacity-50 transition-colors"
            >
              {linkMutation.isPending ? 'Generating link...' : 'Generate Link'}
            </button>
          )}

          {linkMutation.isError && (
            <p className="text-sm text-red-600 dark:text-red-400">
              {linkMutation.error instanceof Error
                ? linkMutation.error.message
                : 'Failed to generate link. Is the Telegram bot configured?'}
            </p>
          )}
        </div>
      )}
    </Card>
  )
}
