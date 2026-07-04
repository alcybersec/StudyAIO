import { Link } from 'react-router-dom'
import { TriangleAlert } from 'lucide-react'
import { useDashboardPendingReviews } from '../../hooks/useApi'

/**
 * Banner above the widget grid. Best-effort: while loading, on error, or
 * with zero pending items it renders nothing — the widgets carry the page.
 */
export function ReviewAlert() {
  const { data: count } = useDashboardPendingReviews()
  if (!count) return null

  return (
    <div className="flex items-center gap-2.5 bg-amber-soft border border-amber/25 rounded-lg px-3.5 py-2.5 mb-5 text-xs font-medium">
      <TriangleAlert size={14} aria-hidden className="shrink-0 text-amber-fg" />
      <p className="flex-1 text-text">
        <strong>
          {count} item{count !== 1 ? 's' : ''}
        </strong>{' '}
        need{count === 1 ? 's' : ''} your review before the pipeline can continue.
      </p>
      <Link
        to="/review"
        className="shrink-0 px-2.5 py-1 rounded-md font-medium bg-surface-1 border border-border hover:bg-surface-2 text-text transition-colors"
      >
        Review now
      </Link>
    </div>
  )
}
