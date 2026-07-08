import { useMemo, useState } from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'
import { Card, EmptyState, ErrorState, SectionLabel, Select, Skeleton } from '../ui'
import { useAnalyticsMastery, useCourses } from '../../hooks/useApi'

export function MasteryBreakdown() {
  const [courseCode, setCourseCode] = useState('')
  const { data: courses } = useCourses()
  const { data, isLoading, error, refetch } = useAnalyticsMastery(courseCode || undefined)

  const chartData = useMemo(() => {
    if (!data?.weeks) return []
    return data.weeks.map((w) => ({
      name: `W${w.week}`,
      course: w.course_code,
      mastered: w.mastered,
      learning: w.learning,
      new: w.new,
      total: w.total,
      mastery_pct: w.mastery_pct,
    }))
  }, [data])

  const totals = useMemo(
    () => ({
      cards: chartData.reduce((s, d) => s + d.total, 0),
      avgMastery:
        chartData.length > 0
          ? Math.round(chartData.reduce((s, d) => s + d.mastery_pct, 0) / chartData.length)
          : 0,
    }),
    [chartData],
  )

  const courseOptions = useMemo(
    () => [
      { value: '', label: 'All courses' },
      ...(courses?.map((c) => ({ value: c.code, label: c.code })) ?? []),
    ],
    [courses],
  )

  if (isLoading) {
    return (
      <Card padding>
        <Skeleton height={12} width={112} className="mb-3" />
        <Skeleton height={240} width="100%" />
      </Card>
    )
  }

  if (error) {
    return (
      <ErrorState
        title="Mastery breakdown couldn't load"
        detail={error instanceof Error ? error.message : undefined}
        onRetry={() => refetch()}
      />
    )
  }

  if (chartData.length === 0) {
    return (
      <Card>
        <EmptyState
          icon="🗂"
          title="No flashcard data yet"
          description="Upload lectures and generate flashcards to see mastery by week."
          actionLabel="Upload lectures"
          actionTo="/upload"
        />
      </Card>
    )
  }

  return (
    <Card padding>
      <div className="flex items-center justify-between gap-3 flex-wrap mb-2">
        <SectionLabel className="mb-0">Mastery by week</SectionLabel>
        {courses && courses.length > 1 && (
          <Select
            className="w-36"
            options={courseOptions}
            value={courseCode}
            onValueChange={setCourseCode}
          />
        )}
      </div>

      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--t-border)" />
          <XAxis
            dataKey="name"
            tick={{ fill: 'var(--t-text-muted)', fontSize: 11 }}
            stroke="var(--t-border)"
          />
          <YAxis tick={{ fill: 'var(--t-text-muted)', fontSize: 11 }} stroke="var(--t-border)" />
          <Tooltip
            contentStyle={{
              backgroundColor: 'var(--t-surface-1)',
              border: '1px solid var(--t-border)',
              borderRadius: '8px',
              color: 'var(--t-text)',
              fontSize: 12,
            }}
            formatter={((value: number, name: string) => [
              value,
              name.charAt(0).toUpperCase() + name.slice(1),
            ]) as never}
          />
          <Legend wrapperStyle={{ fontSize: 12, color: 'var(--t-text-muted)' }} />
          <Bar dataKey="mastered" stackId="a" fill="var(--t-sage)" name="Mastered" />
          <Bar dataKey="learning" stackId="a" fill="var(--t-amber)" name="Learning" />
          <Bar dataKey="new" stackId="a" fill="var(--t-border-strong)" name="New" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>

      <p className="font-mono text-[11px] text-text-faint text-center mt-3">
        {totals.cards} cards · avg mastery {totals.avgMastery}%
      </p>
    </Card>
  )
}
