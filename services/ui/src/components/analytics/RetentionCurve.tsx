import { useMemo, useState } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { Card, EmptyState, ErrorState, SectionLabel, Select, Skeleton } from '../ui'
import { useAnalyticsRetention, useCourses } from '../../hooks/useApi'

export function RetentionCurve() {
  const [courseCode, setCourseCode] = useState('')
  const { data: courses } = useCourses()
  const { data, isLoading, error, refetch } = useAnalyticsRetention(courseCode || undefined)

  const points = useMemo(() => data?.points ?? [], [data])
  const totalReviews = useMemo(
    () => points.reduce((sum, p) => sum + p.card_count, 0),
    [points],
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
        title="Retention curve couldn't load"
        detail={error instanceof Error ? error.message : undefined}
        onRetry={() => refetch()}
      />
    )
  }

  if (points.length === 0 || totalReviews === 0) {
    return (
      <Card>
        <EmptyState
          icon="📈"
          title="Not enough review data"
          description="The retention curve appears once cards have been reviewed across a few intervals."
        />
      </Card>
    )
  }

  return (
    <Card padding>
      <div className="flex items-center justify-between gap-3 flex-wrap mb-2">
        <SectionLabel className="mb-0">Retention curve</SectionLabel>
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
        <LineChart data={points} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--t-border)" />
          <XAxis
            dataKey="interval_bucket"
            label={{
              value: 'Interval (days)',
              position: 'insideBottom',
              offset: -5,
              style: { fill: 'var(--t-text-muted)', fontSize: 12 },
            }}
            tick={{ fill: 'var(--t-text-muted)', fontSize: 11 }}
            stroke="var(--t-border)"
          />
          <YAxis
            domain={[0, 100]}
            label={{
              value: 'Retention %',
              angle: -90,
              position: 'insideLeft',
              style: { fill: 'var(--t-text-muted)', fontSize: 12 },
            }}
            tick={{ fill: 'var(--t-text-muted)', fontSize: 11 }}
            stroke="var(--t-border)"
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'var(--t-surface-1)',
              border: '1px solid var(--t-border)',
              borderRadius: '8px',
              color: 'var(--t-text)',
              fontSize: 12,
            }}
            formatter={((value: number) => [`${value.toFixed(1)}%`, 'Retention']) as never}
            labelFormatter={((label: number) => `${label} day${label !== 1 ? 's' : ''}`) as never}
          />
          <Line
            type="monotone"
            dataKey="retention_pct"
            stroke="var(--t-peri)"
            strokeWidth={2}
            dot={{ r: 4, fill: 'var(--t-peri)' }}
            activeDot={{ r: 6 }}
          />
        </LineChart>
      </ResponsiveContainer>
      <p className="font-mono text-[11px] text-text-faint text-center mt-2">
        based on {totalReviews} card reviews
      </p>
    </Card>
  )
}
