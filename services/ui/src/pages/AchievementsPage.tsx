import { useState } from 'react'
import { useAchievements, useLeaderboard, useXPSummary } from '../hooks/useApi'
import { LoadingSpinner, ErrorBanner, PageHeader } from '../components/ui'
import { AchievementBadge } from '../components/gamification/AchievementBadge'
import { XPBar } from '../components/gamification/XPBar'

type Tab = 'achievements' | 'leaderboard'

const CATEGORIES = ['all', 'study', 'milestone', 'streak', 'mastery'] as const

export function AchievementsPage() {
  const [tab, setTab] = useState<Tab>('achievements')
  const [category, setCategory] = useState<string>('all')

  const { data: xp, isLoading: xpLoading } = useXPSummary()
  const { data: achievements, isLoading: achLoading, error: achError } = useAchievements()
  const { data: leaderboard, isLoading: lbLoading } = useLeaderboard()

  if (xpLoading || achLoading) return <LoadingSpinner label="Loading achievements..." />
  if (achError) return <ErrorBanner message="Failed to load achievements." />

  const filteredAchievements =
    achievements?.achievements.filter(
      (a) => category === 'all' || a.category === category
    ) ?? []

  return (
    <div>
      <PageHeader
        title="Achievements"
        subtitle={
          achievements
            ? `${achievements.earned} / ${achievements.total} unlocked`
            : undefined
        }
      />

      {xp && (
        <div className="mb-6 rounded-lg border border-border bg-surface p-4">
          <XPBar
            level={xp.level}
            totalXP={xp.total_xp}
            progressPct={xp.progress_pct}
            nextThreshold={xp.next_threshold}
          />
        </div>
      )}

      {/* Tab bar */}
      <div className="mb-6 flex gap-1 rounded-lg bg-surface-alt p-1">
        {(['achievements', 'leaderboard'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 rounded-md py-2 text-sm font-medium transition-colors ${
              tab === t
                ? 'bg-surface text-text shadow-sm'
                : 'text-text-muted hover:text-text'
            }`}
          >
            {t === 'achievements' ? 'Achievements' : 'Leaderboard'}
          </button>
        ))}
      </div>

      {tab === 'achievements' && (
        <>
          {/* Category filter */}
          <div className="mb-4 flex flex-wrap gap-2">
            {CATEGORIES.map((cat) => (
              <button
                key={cat}
                onClick={() => setCategory(cat)}
                className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                  category === cat
                    ? 'bg-indigo-100 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300'
                    : 'bg-surface-alt text-text-muted hover:text-text'
                }`}
              >
                {cat.charAt(0).toUpperCase() + cat.slice(1)}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
            {filteredAchievements.map((ach) => (
              <AchievementBadge key={ach.id} achievement={ach} />
            ))}
          </div>

          {filteredAchievements.length === 0 && (
            <p className="text-center text-sm text-text-muted py-8">
              No achievements in this category.
            </p>
          )}
        </>
      )}

      {tab === 'leaderboard' && (
        <div className="rounded-lg border border-border bg-surface overflow-hidden">
          {lbLoading ? (
            <div className="p-8">
              <LoadingSpinner label="Loading leaderboard..." />
            </div>
          ) : !leaderboard?.entries.length ? (
            <p className="p-8 text-center text-sm text-text-muted">
              No leaderboard entries yet. Start studying to earn XP!
            </p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-surface-alt">
                  <th className="px-4 py-2 text-left font-medium text-text-muted">#</th>
                  <th className="px-4 py-2 text-left font-medium text-text-muted">User</th>
                  <th className="px-4 py-2 text-right font-medium text-text-muted">Level</th>
                  <th className="px-4 py-2 text-right font-medium text-text-muted">XP</th>
                </tr>
              </thead>
              <tbody>
                {leaderboard.entries.map((entry) => (
                  <tr key={entry.user_id} className="border-b border-border last:border-0">
                    <td className="px-4 py-2 text-text-muted">{entry.rank}</td>
                    <td className="px-4 py-2 font-medium text-text">{entry.username}</td>
                    <td className="px-4 py-2 text-right">
                      <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-indigo-100 dark:bg-indigo-900/40 text-xs font-bold text-indigo-700 dark:text-indigo-300">
                        {entry.level}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right text-text-muted">
                      {entry.total_xp.toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}
