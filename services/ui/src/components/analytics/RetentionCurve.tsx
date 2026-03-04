import { useState } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { useAnalyticsRetention } from '../../hooks/useApi'
import { useCourses } from '../../hooks/useApi'
import { LoadingSpinner } from '../ui'

export function RetentionCurve() {
  const [courseCode, setCourseCode] = useState<string>('')
  const { data: courses } = useCourses()
  const { data, isLoading, error } = useAnalyticsRetention(courseCode || undefined)

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-sm text-danger">Failed to load retention data.</p>
      </div>
    )
  }

  const points = data?.points ?? []

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <h3 className="text-lg font-semibold text-text">Retention Curve</h3>
        {courses && courses.length > 1 && (
          <select
            value={courseCode}
            onChange={(e) => setCourseCode(e.target.value)}
            className="text-sm rounded-lg border border-border bg-surface text-text px-3 py-1.5 min-h-[36px]"
          >
            <option value="">All courses</option>
            {courses.map((c) => (
              <option key={c.id} value={c.code}>
                {c.code}
              </option>
            ))}
          </select>
        )}
      </div>

      {isLoading && <LoadingSpinner label="Loading retention data..." />}

      {!isLoading && points.length === 0 && (
        <div className="text-center py-12 text-text-muted text-sm">
          Not enough review data to plot a retention curve yet.
        </div>
      )}

      {!isLoading && points.length > 0 && (
        <div className="rounded-lg border border-border bg-surface p-4">
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={points} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis
                dataKey="interval_bucket"
                label={{ value: 'Interval (days)', position: 'insideBottom', offset: -5, style: { fill: 'var(--color-text-muted)', fontSize: 12 } }}
                tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }}
                stroke="var(--color-border)"
              />
              <YAxis
                domain={[0, 100]}
                label={{ value: 'Retention %', angle: -90, position: 'insideLeft', style: { fill: 'var(--color-text-muted)', fontSize: 12 } }}
                tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }}
                stroke="var(--color-border)"
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'var(--color-surface)',
                  border: '1px solid var(--color-border)',
                  borderRadius: '8px',
                  color: 'var(--color-text)',
                  fontSize: 12,
                }}
                formatter={((value: number) => [`${value.toFixed(1)}%`, 'Retention']) as never}
                labelFormatter={((label: number) => `${label} day${label !== 1 ? 's' : ''}`) as never}
              />
              <Line
                type="monotone"
                dataKey="retention_pct"
                stroke="var(--color-primary)"
                strokeWidth={2}
                dot={{ r: 4, fill: 'var(--color-primary)' }}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          </ResponsiveContainer>
          <p className="text-xs text-text-muted text-center mt-2">
            Based on {points.reduce((sum, p) => sum + p.card_count, 0)} card reviews
          </p>
        </div>
      )}
    </div>
  )
}
