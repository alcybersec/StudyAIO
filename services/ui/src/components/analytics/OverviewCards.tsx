import { useMemo } from 'react'
import { Card, EmptyState, ErrorState, SectionLabel, Skeleton } from '../ui'
import { useAnalyticsHeatmap, useAnalyticsOverview, useStreak } from '../../hooks/useApi'
import { weeklyTrend } from './trend'

interface Stat {
  label: string
  value: string
  trend: number[]
  tone: string
}

function Sparkline({ trend, tone }: { trend: number[]; tone: string }) {
  const max = Math.max(...trend)
  if (max <= 0) return null
  const points = trend
    .map((v, i) => `${(i / Math.max(trend.length - 1, 1)) * 64},${18 - (v / max) * 16}`)
    .join(' ')
  return (
    <svg viewBox="0 0 64 20" className="w-16 h-5 shrink-0" aria-hidden>
      <polyline
        points={points}
        fill="none"
        style={{ stroke: tone }}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export function OverviewCards() {
  const { data, isLoading, error, refetch } = useAnalyticsOverview()
  const { data: heatmap } = useAnalyticsHeatmap(91)
  const { data: streak } = useStreak()

  const stats = useMemo<Stat[]>(() => {
    if (!data) return []
    return [
      {
        label: 'Cards reviewed',
        value: data.total_cards_reviewed.toLocaleString(),
        trend: weeklyTrend(heatmap?.days, (d) => d.cards),
        tone: 'var(--t-sage)',
      },
      {
        label: 'Study time',
        value: `${data.total_study_hours.toFixed(1)}h`,
        trend: weeklyTrend(heatmap?.days, (d) => d.minutes),
        tone: 'var(--t-amber)',
      },
      {
        label: 'Mastery rate',
        value: `${Math.round(data.mastery_pct)}%`,
        trend: [],
        tone: 'var(--t-peri)',
      },
      {
        label: 'Streak',
        value: `${streak?.current_streak ?? 0}d`,
        trend: weeklyTrend(heatmap?.days, (d) => d.sessions),
        tone: 'var(--t-sage)',
      },
    ]
  }, [data, heatmap, streak])

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i} padding>
            <Skeleton height={12} width={80} className="mb-2" />
            <Skeleton height={28} width={64} className="mb-2" />
            <Skeleton height={20} width={64} />
          </Card>
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <ErrorState
        title="Analytics overview couldn't load"
        detail={error instanceof Error ? error.message : undefined}
        onRetry={() => refetch()}
      />
    )
  }

  if (!data || (data.total_sessions === 0 && data.total_cards_reviewed === 0)) {
    return (
      <Card>
        <EmptyState
          icon="📊"
          title="No study data yet"
          description="Analytics appear after your first review session. Ten cards is enough to start the picture."
          actionLabel="Start a session"
          actionTo="/study?tab=flashcards"
        />
      </Card>
    )
  }

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {stats.map((s) => (
        <Card key={s.label} padding>
          <SectionLabel>{s.label}</SectionLabel>
          <div className="flex items-end justify-between gap-2">
            <span className="text-2xl font-bold tracking-tight text-text">{s.value}</span>
            {s.trend.length > 1 && <Sparkline trend={s.trend} tone={s.tone} />}
          </div>
        </Card>
      ))}
    </div>
  )
}
