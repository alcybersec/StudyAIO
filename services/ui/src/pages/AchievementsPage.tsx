import { useAchievements, useLeaderboard, useXPSummary } from '../hooks/useApi'
import { useTabRouting } from '../hooks/useTabRouting'
import {
  EmptyState,
  ErrorState,
  PageHeader,
  Skeleton,
  Table,
  TBody,
  TCell,
  THead,
  TRow,
} from '../components/ui'
import { AchievementBadge } from '../components/gamification/AchievementBadge'
import { XPBar } from '../components/gamification/XPBar'

const TABS = ['achievements', 'leaderboard'] as const

const CATEGORIES = ['all', 'study', 'milestone', 'streak', 'mastery'] as const

function XPSection() {
  const { data: xp, isLoading, isError, refetch } = useXPSummary()

  if (isLoading && !xp) {
    return (
      <div
        className="mb-6 rounded-xl border border-border bg-surface-1 p-4 flex items-center gap-3"
        role="status"
        aria-label="Loading XP"
      >
        <Skeleton height={40} width={40} rounded />
        <div className="flex-1 space-y-2">
          <Skeleton height={12} width={120} />
          <Skeleton height={6} width="100%" rounded />
        </div>
      </div>
    )
  }

  if (isError && !xp) {
    return (
      <div className="mb-6">
        <ErrorState compact title="XP progress couldn't load" onRetry={() => refetch()} />
      </div>
    )
  }

  if (!xp) return null

  return (
    <div className="mb-6 rounded-xl border border-border bg-surface-1 p-4">
      <XPBar level={xp.level} totalXP={xp.total_xp} progressPct={xp.progress_pct} nextThreshold={xp.next_threshold} />
    </div>
  )
}

function AchievementsGridSkeleton() {
  return (
    <div
      className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3"
      role="status"
      aria-label="Loading achievements"
    >
      {Array.from({ length: 10 }).map((_, i) => (
        <div key={i} className="rounded-xl border border-border bg-surface-1 p-3 flex flex-col items-center gap-2">
          <Skeleton height={20} width={20} rounded />
          <Skeleton height={12} width="70%" />
          <Skeleton height={8} width={40} />
        </div>
      ))}
    </div>
  )
}

function AchievementsTab({ category, onCategoryChange }: { category: string; onCategoryChange: (c: string) => void }) {
  const { data, isLoading, isError, refetch } = useAchievements()

  if (isLoading && !data) return <AchievementsGridSkeleton />

  if (isError && !data) {
    return <ErrorState title="Achievements couldn't load" onRetry={() => refetch()} />
  }

  if (!data || data.achievements.length === 0) {
    return (
      <EmptyState
        title="No achievements yet"
        description="Upload lectures and study cards to start unlocking achievements."
      />
    )
  }

  const filtered = data.achievements.filter((a) => category === 'all' || a.category === category)

  return (
    <>
      <div className="mb-4 flex flex-wrap gap-2">
        {CATEGORIES.map((cat) => (
          <button
            key={cat}
            onClick={() => onCategoryChange(cat)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
              category === cat
                ? 'bg-peri-soft text-peri-fg'
                : 'bg-surface-2 text-text-muted hover:text-text'
            }`}
          >
            {cat.charAt(0).toUpperCase() + cat.slice(1)}
          </button>
        ))}
      </div>

      {filtered.length > 0 ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
          {filtered.map((ach) => (
            <AchievementBadge key={ach.id} achievement={ach} />
          ))}
        </div>
      ) : (
        <EmptyState compact title="No achievements in this category" description="Try another category filter." />
      )}
    </>
  )
}

function LeaderboardSkeleton() {
  return (
    <div className="p-4 space-y-3" role="status" aria-label="Loading leaderboard">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="flex items-center gap-4">
          <Skeleton height={14} width={24} />
          <Skeleton height={14} width="40%" />
          <Skeleton height={22} width={24} rounded />
          <Skeleton height={14} width={64} />
        </div>
      ))}
    </div>
  )
}

function LeaderboardTab() {
  const { data, isLoading, isError, refetch } = useLeaderboard()

  return (
    <div className="rounded-xl border border-border bg-surface-1 overflow-hidden">
      {isLoading && !data ? (
        <LeaderboardSkeleton />
      ) : isError && !data ? (
        <div className="p-4">
          <ErrorState compact title="Leaderboard couldn't load" onRetry={() => refetch()} />
        </div>
      ) : !data || data.entries.length === 0 ? (
        <EmptyState
          compact
          title="No leaderboard entries yet"
          description="Start studying to earn XP and claim a spot."
        />
      ) : (
        <div className="px-4 py-2">
          <Table>
            <THead>
              <TCell header>#</TCell>
              <TCell header>User</TCell>
              <TCell header align="right">
                Level
              </TCell>
              <TCell header align="right">
                XP
              </TCell>
            </THead>
            <TBody>
              {data.entries.map((entry) => (
                <TRow key={entry.user_id}>
                  <TCell className="font-mono text-[11px] text-text-faint">{entry.rank}</TCell>
                  <TCell className="font-medium text-text">{entry.username}</TCell>
                  <TCell align="right">
                    <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-peri-soft text-xs font-bold text-peri-fg">
                      {entry.level}
                    </span>
                  </TCell>
                  <TCell align="right" className="font-mono text-text-muted">
                    {entry.total_xp.toLocaleString()}
                  </TCell>
                </TRow>
              ))}
            </TBody>
          </Table>
        </div>
      )}
    </div>
  )
}

export function AchievementsPage() {
  const [tab, setTab] = useTabRouting(TABS, 'achievements')
  const [category, setCategory] = useTabRouting(CATEGORIES, 'all', 'category')

  const { data: achievements } = useAchievements()

  return (
    <div>
      <PageHeader
        title="Achievements"
        subtitle={achievements ? `${achievements.earned} / ${achievements.total} unlocked` : undefined}
      />

      <XPSection />

      <div className="mb-6 flex gap-1 rounded-lg bg-surface-2 p-1">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 rounded-md py-2 text-sm font-medium transition-colors ${
              tab === t ? 'bg-surface-1 text-text shadow-sm' : 'text-text-muted hover:text-text'
            }`}
          >
            {t === 'achievements' ? 'Achievements' : 'Leaderboard'}
          </button>
        ))}
      </div>

      {tab === 'achievements' && (
        <AchievementsTab category={category} onCategoryChange={(c) => setCategory(c as (typeof CATEGORIES)[number])} />
      )}
      {tab === 'leaderboard' && <LeaderboardTab />}
    </div>
  )
}
