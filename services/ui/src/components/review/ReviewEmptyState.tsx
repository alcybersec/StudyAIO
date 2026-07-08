import { Link } from 'react-router-dom'
import { CheckCircle2, Inbox } from 'lucide-react'
import { Card } from '../ui'

interface ReviewEmptyStateProps {
  filter: 'pending' | 'resolved' | 'dismissed'
}

/** Empty state per filter — "inbox zero" gets the celebratory sage tint. */
export function ReviewEmptyState({ filter }: ReviewEmptyStateProps) {
  if (filter === 'pending') {
    return (
      <Card className="border-sage/30 bg-sage-soft">
        <div className="flex flex-col items-center justify-center py-10 text-center">
          <CheckCircle2 size={28} strokeWidth={1.5} className="text-sage-fg mb-3" aria-hidden />
          <h3 className="text-lg font-semibold text-text mb-1">
            Inbox zero — nothing needs review
          </h3>
          <p className="text-sm text-text-muted max-w-sm mb-4">
            New uploads land here only when classification confidence is low. You're all
            caught up.
          </p>
          <Link
            to="/upload"
            className="inline-flex items-center px-3.5 py-2 text-sm font-medium rounded-lg bg-surface-1 text-text border border-border hover:bg-surface-2 transition-colors"
          >
            Upload more lectures
          </Link>
        </div>
      </Card>
    )
  }

  return (
    <Card>
      <div className="flex flex-col items-center justify-center py-10 text-center">
        <Inbox size={28} strokeWidth={1.5} className="text-text-faint mb-3" aria-hidden />
        <h3 className="text-lg font-semibold text-text mb-1">No {filter} items</h3>
        <p className="text-sm text-text-muted max-w-sm">
          Items you {filter === 'resolved' ? 'approve or correct' : 'dismiss'} show up here.
        </p>
      </div>
    </Card>
  )
}
