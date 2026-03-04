import { useStreak, useStudyStats } from '../../hooks/useApi'
import { Card, LoadingSpinner } from '../ui'

export function HistoryTab() {
  const { data: streak, isLoading: loadingStreak } = useStreak()
  const { data: stats, isLoading: loadingStats } = useStudyStats()

  if (loadingStreak || loadingStats) return <LoadingSpinner label="Loading stats..." />

  return (
    <div className="space-y-6">
      {/* Streak */}
      <Card>
        <div className="flex items-center gap-4">
          <div className="text-4xl">{(streak?.current_streak ?? 0) > 0 ? '\u{1F525}' : '\u{1F9CA}'}</div>
          <div>
            <div className="text-2xl font-bold text-text">{streak?.current_streak ?? 0} day streak</div>
            <div className="text-sm text-text-muted">
              Longest streak: {streak?.longest_streak ?? 0} days
            </div>
          </div>
        </div>
      </Card>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <div className="text-center">
            <div className="text-2xl font-bold text-text">{stats?.due_today ?? 0}</div>
            <div className="text-xs text-text-muted mt-1">Due Today</div>
          </div>
        </Card>
        <Card>
          <div className="text-center">
            <div className="text-2xl font-bold text-text">{stats?.learning ?? 0}</div>
            <div className="text-xs text-text-muted mt-1">Learning</div>
          </div>
        </Card>
        <Card>
          <div className="text-center">
            <div className="text-2xl font-bold text-text">{stats?.total ?? 0}</div>
            <div className="text-xs text-text-muted mt-1">Total Cards</div>
          </div>
        </Card>
        <Card>
          <div className="text-center">
            <div className="text-2xl font-bold text-text">{stats?.mastered ?? 0}</div>
            <div className="text-xs text-text-muted mt-1">Mastered</div>
          </div>
        </Card>
      </div>

      {/* Tip */}
      <div className="text-center py-4 text-sm text-text-muted">
        Study consistently each day to maintain your streak and maximize retention.
      </div>
    </div>
  )
}
