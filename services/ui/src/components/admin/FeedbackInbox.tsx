import { useState } from 'react'
import { useAdminFeedback, useSetFeedbackStatus } from '../../hooks/useApi'
import { Button, ErrorState, Skeleton } from '../ui'
import type { FeedbackStatus } from '../../types'

const FILTERS: { value: FeedbackStatus | undefined; label: string }[] = [
  { value: 'new', label: 'New' },
  { value: 'triaged', label: 'Triaged' },
  { value: 'closed', label: 'Closed' },
  { value: undefined, label: 'All' },
]

const KIND_LABELS: Record<string, string> = {
  bug: 'Broke',
  confusing: 'Confusing',
  idea: 'Idea',
}

/**
 * What users have actually said.
 *
 * Feedback nobody reads is worse than no feedback, because it looks like a
 * channel. This is the other half of the submit box.
 */
export function FeedbackInbox() {
  const [status, setStatus] = useState<FeedbackStatus | undefined>('new')
  const { data, isLoading, isError, refetch } = useAdminFeedback(status)
  const setFeedbackStatus = useSetFeedbackStatus()

  if (isLoading) {
    return (
      <div className="bg-surface-1 rounded-xl border border-border p-4 space-y-3">
        <Skeleton height={12} width={100} />
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} height={44} />
        ))}
      </div>
    )
  }

  if (isError && !data) {
    return <ErrorState compact title="Feedback couldn't load" onRetry={() => refetch()} />
  }

  if (!data) return null

  return (
    <section className="bg-surface-1 rounded-xl border border-border p-4 space-y-3">
      <header className="flex items-center justify-between gap-3 flex-wrap">
        <h2 className="text-sm font-medium text-text">
          Feedback
          {data.counts.new > 0 && (
            <span className="ml-2 px-1.5 py-0.5 rounded-full text-[11px] bg-sage-soft text-text">
              {data.counts.new} new
            </span>
          )}
        </h2>
        <div className="flex gap-1">
          {FILTERS.map((f) => (
            <button
              key={f.label}
              type="button"
              aria-pressed={status === f.value}
              onClick={() => setStatus(f.value)}
              className={
                status === f.value
                  ? 'px-2 py-0.5 rounded text-[11px] bg-surface-2 text-text border border-border'
                  : 'px-2 py-0.5 rounded text-[11px] text-text-muted'
              }
            >
              {f.label}
            </button>
          ))}
        </div>
      </header>

      {data.items.length === 0 ? (
        <p className="text-xs text-text-faint">
          {status === 'new' ? 'Nothing new.' : 'Nothing here.'}
        </p>
      ) : (
        <ul className="space-y-2">
          {data.items.map((item) => (
            <li key={item.id} className="rounded-lg bg-surface-2 border border-border p-3 space-y-1.5">
              <div className="flex items-center gap-2 flex-wrap text-[11px] text-text-muted">
                <span className="font-medium text-text">
                  {KIND_LABELS[item.kind] ?? item.kind}
                </span>
                {item.user_email && <span>{item.user_email}</span>}
                {/* The two fields that make a report reproducible rather than
                    just sympathetic. */}
                {item.route && <code className="font-mono">{item.route}</code>}
                {item.app_version && <code className="font-mono">{item.app_version}</code>}
              </div>

              <p className="text-xs text-text whitespace-pre-wrap break-words">{item.message}</p>

              <div className="flex gap-1.5">
                {item.status !== 'triaged' && (
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={setFeedbackStatus.isPending}
                    onClick={() =>
                      setFeedbackStatus.mutate({ id: item.id, status: 'triaged' })
                    }
                  >
                    Triaged
                  </Button>
                )}
                {item.status !== 'closed' && (
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={setFeedbackStatus.isPending}
                    onClick={() => setFeedbackStatus.mutate({ id: item.id, status: 'closed' })}
                  >
                    Close
                  </Button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
