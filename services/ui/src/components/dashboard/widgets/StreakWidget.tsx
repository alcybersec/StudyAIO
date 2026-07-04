import { memo } from 'react'
import { Flame } from 'lucide-react'
import { useDashboardStreak } from '../../../hooks/useApi'
import { Skeleton } from '../../ui'
import { WidgetShell } from './WidgetShell'
import { selectWidgetState } from './widgetState'

function StreakSkeleton() {
  return (
    <div>
      <Skeleton height={28} width={110} />
      <Skeleton height={12} width={160} className="mt-3" />
    </div>
  )
}

export const StreakWidget = memo(function StreakWidget() {
  const { data, isLoading, isError, refetch } = useDashboardStreak()
  const state = selectWidgetState({
    isLoading,
    isError,
    hasData: data !== undefined,
    isEmpty: !data || (data.current_streak === 0 && data.longest_streak === 0),
  })

  return (
    <WidgetShell
      title="Streak"
      state={state}
      onRetry={() => refetch()}
      emptyTitle="No sessions yet"
      emptyHint="Review a few cards to start a streak."
      emptyActionLabel="Start studying"
      emptyActionTo="/study"
      skeleton={<StreakSkeleton />}
    >
      {data && (
        <>
          <div className="text-2xl font-bold text-amber-fg inline-flex items-center gap-1.5">
            <Flame size={20} aria-hidden />
            {data.current_streak} day{data.current_streak !== 1 ? 's' : ''}
          </div>
          <div className="text-[11px] text-text-faint font-mono mt-2">
            {data.longest_streak > data.current_streak
              ? `best ${data.longest_streak} days`
              : 'personal best — keep it alive'}
          </div>
        </>
      )}
    </WidgetShell>
  )
})
