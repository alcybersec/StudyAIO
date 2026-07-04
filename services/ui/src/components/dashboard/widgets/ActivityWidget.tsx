import { memo } from 'react'
import { useDashboardActivity } from '../../../hooks/useApi'
import { Skeleton, StatusBadge } from '../../ui'
import { WidgetShell } from './WidgetShell'
import { selectWidgetState } from './widgetState'
import { relativeTime } from './format'

function ActivitySkeleton() {
  return (
    <div className="space-y-2.5">
      {[0, 1, 2].map((i) => (
        <div key={i} className="flex items-center justify-between gap-3">
          <Skeleton height={14} width="60%" />
          <Skeleton height={12} width={48} />
        </div>
      ))}
    </div>
  )
}

export const ActivityWidget = memo(function ActivityWidget() {
  const { data, isLoading, isError, refetch } = useDashboardActivity()
  const state = selectWidgetState({
    isLoading,
    isError,
    hasData: data !== undefined,
    isEmpty: !data || data.length === 0,
  })

  return (
    <WidgetShell
      title="Recent activity"
      state={state}
      onRetry={() => refetch()}
      emptyTitle="No activity yet"
      emptyHint="Pipeline runs show up here as your files are processed."
      skeleton={<ActivitySkeleton />}
    >
      <ul className="divide-y divide-border">
        {data?.slice(0, 6).map((item) => (
          <li key={item.pipeline_run_id} className="flex items-center gap-3 py-1.5">
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-text truncate">{item.filename ?? 'Unknown file'}</p>
              <p className="text-[10px] font-mono text-text-faint mt-0.5">{item.stage}</p>
            </div>
            <StatusBadge status={item.status} />
            <span className="text-[10px] font-mono text-text-faint shrink-0 w-14 text-right">
              {relativeTime(item.completed_at ?? item.started_at)}
            </span>
          </li>
        ))}
      </ul>
    </WidgetShell>
  )
})
