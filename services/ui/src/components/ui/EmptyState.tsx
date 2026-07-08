import { Link } from 'react-router-dom'

interface EmptyStateProps {
  icon?: string
  title: string
  description?: string
  actionLabel?: string
  actionTo?: string
  onAction?: () => void
  /** Tighter spacing for use inside dashboard widgets and dense panels. */
  compact?: boolean
}

export function EmptyState({ icon = '\u{1F4DA}', title, description, actionLabel, actionTo, onAction, compact }: EmptyStateProps) {
  const actionClass = compact
    ? 'inline-flex items-center px-3 py-1.5 bg-sage text-on-accent text-xs font-medium rounded-md hover:bg-sage-hover transition-colors'
    : 'inline-flex items-center px-4 py-2 bg-sage text-on-accent text-sm font-medium rounded-lg hover:bg-sage-hover transition-colors'
  return (
    <div className={`flex flex-col items-center justify-center text-center ${compact ? 'py-4' : 'py-12'}`}>
      <span className={compact ? 'text-xl mb-2' : 'text-4xl mb-3'}>{icon}</span>
      {compact ? (
        <p className="text-sm font-medium text-text">{title}</p>
      ) : (
        <h3 className="text-lg font-semibold text-text mb-1">{title}</h3>
      )}
      {description && (
        <p className={`text-text-muted max-w-sm ${compact ? 'text-xs mt-1 mb-3' : 'text-sm mb-4'}`}>{description}</p>
      )}
      {actionLabel && actionTo && (
        <Link to={actionTo} className={actionClass}>
          {actionLabel}
        </Link>
      )}
      {actionLabel && onAction && !actionTo && (
        <button onClick={onAction} className={actionClass}>
          {actionLabel}
        </button>
      )}
    </div>
  )
}
