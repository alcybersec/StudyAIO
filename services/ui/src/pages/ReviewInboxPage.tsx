import { useCallback, useMemo, useState } from 'react'
import { Card, ErrorState, PageHeader, Skeleton, toast } from '../components/ui'
import { ReviewRow } from '../components/review/ReviewRow'
import { ReviewEmptyState } from '../components/review/ReviewEmptyState'
import { ReviewFilterPills, type ReviewFilter } from '../components/review/ReviewFilterPills'
import { approveResolution } from '../components/review/reviewUtils'
import {
  useCourses,
  useDismissReview,
  usePendingReviews,
  useReviewItems,
  useResolveReview,
} from '../hooks/useApi'
import { useOnlineStatus } from '../hooks/useOnlineStatus'
import { useTriageKeys } from '../hooks/useTriageKeys'
import type { ReviewItem } from '../types'

function RowSkeleton() {
  return (
    <div className="flex items-center gap-4 px-3 py-3">
      <div className="flex-1 space-y-2">
        <Skeleton className="h-3.5 w-48" />
        <Skeleton className="h-3 w-72" />
      </div>
      <Skeleton className="h-6 w-40" />
    </div>
  )
}

export function ReviewInboxPage() {
  const [filter, setFilter] = useState<ReviewFilter>('pending')
  const [rawFocus, setRawFocus] = useState(0)
  const [editingId, setEditingId] = useState<string | null>(null)

  const { data, isLoading, error, refetch } = useReviewItems(filter)
  const { data: pendingItems } = usePendingReviews()
  const { data: courses } = useCourses()
  const resolve = useResolveReview()
  const dismiss = useDismissReview()
  const online = useOnlineStatus()

  const items = useMemo(() => data ?? [], [data])
  const focusIndex = items.length === 0 ? 0 : Math.min(rawFocus, items.length - 1)
  const focusedItem: ReviewItem | undefined = items[focusIndex]
  const busy = resolve.isPending || dismiss.isPending

  const changeFilter = (next: ReviewFilter) => {
    setFilter(next)
    setRawFocus(0)
    setEditingId(null)
  }

  const handleResolve = useCallback(
    async (item: ReviewItem, resolution: Record<string, unknown>) => {
      try {
        await resolve.mutateAsync({ reviewId: item.id, resolution })
        setEditingId(null)
        toast.success('Review item resolved.')
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Failed to resolve the item.')
      }
    },
    [resolve],
  )

  const handleDismiss = useCallback(
    async (item: ReviewItem) => {
      try {
        await dismiss.mutateAsync(item.id)
        setEditingId(null)
        toast.success('Review item dismissed.')
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Failed to dismiss the item.')
      }
    },
    [dismiss],
  )

  const handleApprove = useCallback(
    (item: ReviewItem) => {
      if (busy) return
      const resolution = approveResolution(item)
      // No usable guess to approve — fall back to the inline editor.
      if (resolution === null) {
        setEditingId(item.id)
        return
      }
      void handleResolve(item, resolution)
    },
    [busy, handleResolve],
  )

  const keyHandlers = useMemo(
    () => ({
      onMove: (delta: 1 | -1) =>
        setRawFocus(Math.max(0, Math.min(items.length - 1, focusIndex + delta))),
      onApprove: () => {
        if (focusedItem) handleApprove(focusedItem)
      },
      onEdit: () => {
        if (focusedItem) setEditingId(focusedItem.id)
      },
      onDismiss: () => {
        if (focusedItem && !busy) void handleDismiss(focusedItem)
      },
      onCancelEdit: () => setEditingId(null),
    }),
    [items.length, focusIndex, focusedItem, busy, handleApprove, handleDismiss],
  )

  useTriageKeys(filter === 'pending' && items.length > 0, editingId !== null, keyHandlers)

  const pendingCount = pendingItems?.length ?? 0

  return (
    <div>
      <PageHeader
        title="Review inbox"
        subtitle="Files the pipeline wasn't confident about — approve, correct, or dismiss."
        actions={
          <ReviewFilterPills filter={filter} pendingCount={pendingCount} onChange={changeFilter} />
        }
      />

      {isLoading && (
        <Card padding={false}>
          <div className="divide-y divide-border" role="status" aria-label="Loading review items">
            <RowSkeleton />
            <RowSkeleton />
            <RowSkeleton />
          </div>
        </Card>
      )}

      {error && (
        <ErrorState
          title={online ? "Review inbox couldn't load" : "You're offline"}
          detail={
            online
              ? error instanceof Error
                ? error.message
                : undefined
              : 'The review inbox needs a connection. It will load again once you are back online.'
          }
          onRetry={() => refetch()}
        />
      )}

      {!error && !isLoading && items.length === 0 && <ReviewEmptyState filter={filter} />}

      {!error && items.length > 0 && (
        <>
          <Card padding={false} className="overflow-hidden">
            <ul className="divide-y divide-border">
              {items.map((item, index) => (
                <ReviewRow
                  key={item.id}
                  item={item}
                  focused={index === focusIndex}
                  editing={item.id === editingId}
                  busy={busy}
                  courses={courses ?? []}
                  onFocus={() => setRawFocus(index)}
                  onApprove={() => handleApprove(item)}
                  onEdit={() => setEditingId(item.id)}
                  onDismiss={() => void handleDismiss(item)}
                  onConfirmEdit={(resolution) => void handleResolve(item, resolution)}
                  onCancelEdit={() => setEditingId(null)}
                />
              ))}
            </ul>
          </Card>

          {filter === 'pending' && (
            <p className="text-[11px] font-mono text-text-faint mt-3 text-center">
              j/k navigate · a approve · e edit · d dismiss
            </p>
          )}
        </>
      )}
    </div>
  )
}
