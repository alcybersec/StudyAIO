import { Link } from 'react-router-dom'

interface ReviewAlertProps {
  count: number
}

export function ReviewAlert({ count }: ReviewAlertProps) {
  if (count === 0) return null

  return (
    <div className="flex items-center gap-3 px-4 py-3 bg-amber-50 border border-amber-200 rounded-xl mb-6">
      <span className="text-amber-600 text-lg shrink-0">{'\u26A0'}</span>
      <p className="text-sm text-amber-800 flex-1">
        <strong>{count} item{count !== 1 ? 's' : ''}</strong> need{count === 1 ? 's' : ''} your review before the pipeline can continue.
      </p>
      <Link
        to="/review"
        className="shrink-0 px-3 py-1.5 text-sm font-medium text-amber-700 bg-amber-100 hover:bg-amber-200 rounded-lg transition-colors"
      >
        Review now
      </Link>
    </div>
  )
}
