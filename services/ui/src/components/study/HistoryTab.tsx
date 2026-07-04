import { Flame, Snowflake } from 'lucide-react'
import { useAnalyticsHeatmap, useStreak, useStudyStats } from '../../hooks/useApi'
import { useOnlineStatus } from '../../hooks/useOnlineStatus'
import { Card, EmptyState, ErrorState, Skeleton, Table, TBody, TCell, THead, TRow } from '../ui'
import { recentActivity } from '../../lib/studyHistory'

function HistorySkeleton() {
  return (
    <div className="space-y-6" aria-busy="true">
      <Card>
        <div className="flex items-center gap-4">
          <Skeleton width={40} height={40} rounded />
          <div className="space-y-2">
            <Skeleton width={160} height={22} />
            <Skeleton width={120} height={14} />
          </div>
        </div>
      </Card>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i}>
            <div className="flex flex-col items-center gap-2">
              <Skeleton width={48} height={26} />
              <Skeleton width={64} height={12} />
            </div>
          </Card>
        ))}
      </div>
      <Card padding={false} className="p-4">
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} height={28} />
          ))}
        </div>
      </Card>
    </div>
  )
}

export function HistoryTab() {
  const streakQuery = useStreak()
  const statsQuery = useStudyStats()
  const heatmapQuery = useAnalyticsHeatmap(30)
  const online = useOnlineStatus()

  const isLoading = streakQuery.isLoading || statsQuery.isLoading || heatmapQuery.isLoading
  const error = streakQuery.error ?? statsQuery.error ?? heatmapQuery.error

  const retryAll = () => {
    void streakQuery.refetch()
    void statsQuery.refetch()
    void heatmapQuery.refetch()
  }

  if (error) {
    return (
      <ErrorState
        title={online ? "Study history couldn't load" : "You're offline"}
        detail={error instanceof Error ? error.message : undefined}
        onRetry={retryAll}
      />
    )
  }
  if (!online && (!streakQuery.data || !statsQuery.data || !heatmapQuery.data)) {
    return (
      <ErrorState
        title="You're offline"
        detail="Study history hasn't been cached. It will load once you're back online."
        onRetry={retryAll}
      />
    )
  }
  if (isLoading || !streakQuery.data || !statsQuery.data || !heatmapQuery.data) {
    return <HistorySkeleton />
  }

  const streak = streakQuery.data
  const stats = statsQuery.data
  const activity = recentActivity(heatmapQuery.data.days)

  const statTiles: { label: string; value: number }[] = [
    { label: 'Due today', value: stats.due_today },
    { label: 'Learning', value: stats.learning },
    { label: 'Total cards', value: stats.total },
    { label: 'Mastered', value: stats.mastered },
  ]

  return (
    <div className="space-y-6">
      {/* Streak */}
      <Card>
        <div className="flex items-center gap-4">
          <div
            className={`w-10 h-10 rounded-full flex items-center justify-center ${
              streak.current_streak > 0 ? 'bg-amber-soft' : 'bg-surface-2'
            }`}
          >
            {streak.current_streak > 0 ? (
              <Flame size={20} className="text-amber-fg" aria-hidden />
            ) : (
              <Snowflake size={20} className="text-text-faint" aria-hidden />
            )}
          </div>
          <div>
            <div className="text-2xl font-bold text-text">
              {streak.current_streak} day streak
            </div>
            <div className="text-sm text-text-muted">
              Longest streak: {streak.longest_streak} days
            </div>
          </div>
        </div>
      </Card>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {statTiles.map((tile) => (
          <Card key={tile.label}>
            <div className="text-center">
              <div className="text-2xl font-bold font-mono text-text">{tile.value}</div>
              <div className="text-xs text-text-muted mt-1">{tile.label}</div>
            </div>
          </Card>
        ))}
      </div>

      {/* Recent sessions */}
      <div>
        <p className="text-[10px] font-mono font-medium uppercase tracking-[0.1em] text-text-faint mb-2">
          Last 30 days
        </p>
        {activity.length === 0 ? (
          <EmptyState
            title="No study activity yet"
            description="Sessions you complete will show up here. Start with today's plan."
          />
        ) : (
          <Card padding={false} className="px-4 py-2">
            <Table>
              <THead>
                <TCell header>Date</TCell>
                <TCell header align="right">Sessions</TCell>
                <TCell header align="right">Cards</TCell>
                <TCell header align="right">Minutes</TCell>
              </THead>
              <TBody>
                {activity.map((day) => (
                  <TRow key={day.date}>
                    <TCell className="font-mono text-text">{day.date}</TCell>
                    <TCell align="right" className="font-mono text-text-muted">
                      {day.sessions}
                    </TCell>
                    <TCell align="right" className="font-mono text-text-muted">
                      {day.cards}
                    </TCell>
                    <TCell align="right" className="font-mono text-text-muted">
                      {day.minutes}
                    </TCell>
                  </TRow>
                ))}
              </TBody>
            </Table>
          </Card>
        )}
      </div>
    </div>
  )
}
