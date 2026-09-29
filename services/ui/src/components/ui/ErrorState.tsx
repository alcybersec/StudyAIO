import { useTranslation } from 'react-i18next'
import { RefreshCw } from 'lucide-react'
import { Button } from './Button'

interface ErrorStateProps {
  title?: string
  detail?: string
  onRetry?: () => void
  compact?: boolean
}

export function ErrorState({ title, detail, onRetry, compact }: ErrorStateProps) {
  const { t } = useTranslation()

  return (
    <div
      role="alert"
      className={`border border-red/30 bg-red-soft rounded-xl ${compact ? 'p-3' : 'p-5'} flex flex-col items-start gap-2`}
    >
      <p className="text-sm font-medium text-text">{title ?? t("This couldn't load")}</p>
      <p className="text-xs text-text-muted">
        {t('The rest of the app is fine — this section hit a problem. Retrying usually fixes it.')}
      </p>
      <div className="flex items-center gap-3 mt-1">
        {onRetry && (
          <Button variant="secondary" size="sm" onClick={onRetry}>
            <RefreshCw size={12} aria-hidden /> {t('Retry')}
          </Button>
        )}
        {detail && (
          <details className="text-xs text-text-faint">
            <summary className="cursor-pointer hover:text-text-muted">{t('details')}</summary>
            <code className="font-mono text-[11px] block mt-1 max-w-md">{detail}</code>
          </details>
        )}
      </div>
    </div>
  )
}
