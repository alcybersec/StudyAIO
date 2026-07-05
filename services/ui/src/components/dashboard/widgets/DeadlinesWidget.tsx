import { memo, useMemo } from 'react'
import { useDashboardDeadlines } from '../../../hooks/useApi'
import { Skeleton } from '../../ui'
import { WidgetShell } from './WidgetShell'
import { selectWidgetState } from './widgetState'
import { daysUntil, deadlineToneClass } from './format'

function DeadlinesSkeleton() {
  return (
    <div className="space-y-2.5">
      {[0, 1, 2].map((i) => (
        <div key={i} className="flex items-center justify-between gap-3">
          <Skeleton height={14} width="65%" />
          <Skeleton height={12} width={56} />
        </div>
      ))}
    </div>
  )
}

export const DeadlinesWidget = memo(function DeadlinesWidget() {
  const { data, isLoading, isError, refetch } = useDashboardDeadlines()
  // eslint-disable-next-line react-hooks/purity -- capture "now" once per mount for stable countdowns
  const now = useMemo(() => Date.now(), [])
  const state = selectWidgetState({
    isLoading,
    isError,
    hasData: data !== undefined,
    isEmpty: !data || data.length === 0,
  })

  return (
    <WidgetShell
      title="Upcoming deadlines"
      state={state}
      onRetry={() => refetch()}
      emptyTitle="No deadlines"
      emptyHint="Import a course outline in Course Ops to track deadlines."
      skeleton={<DeadlinesSkeleton />}
    >
      <ul className="text-[13px] divide-y divide-border">
        {data?.map((d) => {
          const days = daysUntil(d.due_date, now)
          return (
            <li key={d.id} className="flex items-center justify-between py-1.5">
              <span className="flex items-center gap-2 min-w-0">
                <span className="font-mono text-[10px] text-text-faint shrink-0">{d.course_code}</span>
                <span className="truncate text-text">{d.title}</span>
                {!d.is_confirmed && <span className="text-[10px] text-amber-fg shrink-0">unconfirmed</span>}
              </span>
              <span className={`text-xs font-semibold shrink-0 ml-3 ${deadlineToneClass(days)}`}>
                {days <= 0 ? 'Today' : `${days}d`}
              </span>
            </li>
          )
        })}
      </ul>
    </WidgetShell>
  )
})
