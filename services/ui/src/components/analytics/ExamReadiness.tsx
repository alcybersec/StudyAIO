import { useMemo } from 'react'
import {
  RadialBarChart,
  RadialBar,
  ResponsiveContainer,
  PolarAngleAxis,
} from 'recharts'
import { useAnalyticsReadiness } from '../../hooks/useApi'
import { Skeleton } from '../ui'

interface ExamReadinessProps {
  examId: string
}

function ScoreItem({ label, value, max }: { label: string; value: number; max: number }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="text-text-muted">{label}</span>
      <span className="font-medium text-text">{pct}%</span>
    </div>
  )
}

export function ExamReadiness({ examId }: ExamReadinessProps) {
  const { data, isLoading, error } = useAnalyticsReadiness(examId)

  const gaugeData = useMemo(() => {
    if (!data) return [{ value: 0, fill: 'var(--color-primary)' }]
    return [{ value: data.readiness_score, fill: 'var(--color-primary)' }]
  }, [data])

  if (error) return null

  if (isLoading) {
    return (
      <div className="rounded-lg border border-border bg-surface p-4 space-y-3">
        <Skeleton height={20} width="60%" />
        <Skeleton height={100} width="100%" />
      </div>
    )
  }

  if (!data) return null

  const scoreColor = data.readiness_score >= 70
    ? 'text-green-600 dark:text-green-400'
    : data.readiness_score >= 40
      ? 'text-yellow-600 dark:text-yellow-400'
      : 'text-red-600 dark:text-red-400'

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex items-start justify-between mb-2">
        <div className="min-w-0">
          <h4 className="text-sm font-semibold text-text truncate">{data.title}</h4>
          <p className="text-xs text-text-muted">
            {data.days_remaining > 0
              ? `${data.days_remaining} day${data.days_remaining !== 1 ? 's' : ''} remaining`
              : 'Past due'}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-4">
        {/* Gauge */}
        <div className="w-24 h-24 shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <RadialBarChart
              cx="50%"
              cy="50%"
              innerRadius="70%"
              outerRadius="100%"
              barSize={8}
              data={gaugeData}
              startAngle={90}
              endAngle={-270}
            >
              <PolarAngleAxis type="number" domain={[0, 100]} tick={false} angleAxisId={0} />
              <RadialBar
                background
                dataKey="value"
                cornerRadius={4}
                angleAxisId={0}
              />
            </RadialBarChart>
          </ResponsiveContainer>
          <p className={`text-center -mt-14 text-lg font-bold ${scoreColor}`}>
            {Math.round(data.readiness_score)}
          </p>
          <p className="text-center text-[10px] text-text-muted mt-0.5">Readiness</p>
        </div>

        {/* Score breakdown */}
        <div className="flex-1 space-y-1.5 min-w-0">
          <ScoreItem label="Mastery" value={data.flashcard_mastered} max={data.flashcard_total} />
          <ScoreItem label="Quiz accuracy" value={data.quiz_correct} max={data.quiz_total} />
          <ScoreItem label="Consistency" value={data.study_days_last_week} max={7} />
          {data.weak_weeks.length > 0 && (
            <div className="text-[10px] text-text-muted pt-1 border-t border-border">
              Weak: Week{data.weak_weeks.length > 1 ? 's' : ''} {data.weak_weeks.join(', ')}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
