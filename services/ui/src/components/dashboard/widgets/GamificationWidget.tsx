import { memo } from 'react'
import { useDashboardGamification } from '../../../hooks/useApi'
import { Badge, Skeleton } from '../../ui'
import { WidgetShell } from './WidgetShell'
import { selectWidgetState } from './widgetState'

function GamificationSkeleton() {
  return (
    <div>
      <Skeleton height={6} width="100%" className="mt-1" />
      <Skeleton height={12} width={120} className="mt-2" />
      <Skeleton height={12} width="80%" className="mt-3" />
    </div>
  )
}

export const GamificationWidget = memo(function GamificationWidget() {
  const { data, isLoading, isError, refetch } = useDashboardGamification()
  const state = selectWidgetState({
    isLoading,
    isError,
    hasData: data !== undefined,
    isEmpty: !data,
  })

  const xpToNext = data?.next_threshold != null ? data.next_threshold - data.total_xp : null

  return (
    <WidgetShell
      title={data ? `Level ${data.level} · ${data.total_xp.toLocaleString()} XP` : 'Progress'}
      state={state}
      onRetry={() => refetch()}
      emptyTitle="No XP yet"
      emptyHint="Study a few cards to start earning XP."
      skeleton={<GamificationSkeleton />}
    >
      {data && (
        <>
          <div className="h-1.5 bg-surface-2 rounded-full overflow-hidden mt-1">
            <div className="h-full bg-peri rounded-full" style={{ width: `${Math.min(data.progress_pct, 100)}%` }} />
          </div>
          <div className="text-[11px] text-text-faint mt-2 font-mono">
            {xpToNext != null ? `${xpToNext.toLocaleString()} XP to level ${data.level + 1}` : 'max level reached'}
          </div>
          {data.daily_challenge_description && (
            <div className="text-xs text-text-muted mt-3 flex items-center gap-1.5">
              <Badge variant={data.daily_challenge_completed ? 'success' : 'info'}>
                {data.daily_challenge_completed ? 'done' : 'daily'}
              </Badge>
              <span className="truncate">{data.daily_challenge_description}</span>
              <span className="font-mono text-[10px] text-text-faint shrink-0 ml-auto">
                {data.daily_challenge_progress}/{data.daily_challenge_target}
              </span>
            </div>
          )}
        </>
      )}
    </WidgetShell>
  )
})
