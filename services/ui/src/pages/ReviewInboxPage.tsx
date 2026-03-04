import { useState } from 'react'
import { useReviewItems, useResolveReview, useDismissReview } from '../hooks/useApi'
import { PageHeader, LoadingSpinner, EmptyState } from '../components/ui'
import { ReviewCard } from '../components/review/ReviewCard'

type FilterTab = 'pending' | 'resolved' | 'dismissed'

const filterTabs: { id: FilterTab; label: string }[] = [
  { id: 'pending', label: 'Pending' },
  { id: 'resolved', label: 'Resolved' },
  { id: 'dismissed', label: 'Dismissed' },
]

export function ReviewInboxPage() {
  const [activeFilter, setActiveFilter] = useState<FilterTab>('pending')
  const { data, isLoading, error } = useReviewItems(activeFilter)
  const resolve = useResolveReview()
  const dismiss = useDismissReview()

  const [feedback, setFeedback] = useState<{ ok: boolean; message: string } | null>(null)

  const handleResolve = async (reviewId: string, resolution: Record<string, unknown>) => {
    setFeedback(null)
    try {
      await resolve.mutateAsync({ reviewId, resolution })
      setFeedback({ ok: true, message: 'Review item resolved successfully.' })
    } catch (err) {
      setFeedback({ ok: false, message: err instanceof Error ? err.message : 'Failed to resolve.' })
    }
  }

  const handleDismiss = async (reviewId: string) => {
    setFeedback(null)
    try {
      await dismiss.mutateAsync(reviewId)
      setFeedback({ ok: true, message: 'Review item dismissed.' })
    } catch (err) {
      setFeedback({ ok: false, message: err instanceof Error ? err.message : 'Failed to dismiss.' })
    }
  }

  return (
    <div>
      <PageHeader
        title="Review Inbox"
        subtitle={data ? `${data.length} ${activeFilter} item${data.length !== 1 ? 's' : ''}` : undefined}
      />

      {/* Feedback toast */}
      {feedback && (
        <div className={`mb-4 px-4 py-2.5 rounded-lg text-sm ${feedback.ok ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400' : 'bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-400'}`}>
          {feedback.message}
        </div>
      )}

      {/* Filter tabs */}
      <div className="flex items-center gap-1 mb-6">
        {filterTabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => { setActiveFilter(tab.id); setFeedback(null) }}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
              activeFilter === tab.id
                ? 'bg-primary/10 text-primary'
                : 'text-text-muted hover:text-text hover:bg-surface-alt'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {isLoading && <LoadingSpinner label="Loading review items..." />}

      {error && <EmptyState icon="!" title="Failed to load reviews" description="Check that the API is running." />}

      {data && data.length === 0 && (
        <EmptyState
          icon={activeFilter === 'pending' ? '\u2713' : '\u{1F4CB}'}
          title={activeFilter === 'pending' ? 'All caught up!' : `No ${activeFilter} items`}
          description={activeFilter === 'pending' ? 'There are no items waiting for your review.' : undefined}
        />
      )}

      {data && data.length > 0 && (
        <div className="space-y-4">
          {data.map((item) => (
            <ReviewCard
              key={item.id}
              item={item}
              onResolve={handleResolve}
              onDismiss={handleDismiss}
              isResolving={resolve.isPending}
              isDismissing={dismiss.isPending}
            />
          ))}
        </div>
      )}
    </div>
  )
}
