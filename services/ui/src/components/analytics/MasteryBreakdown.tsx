import { useState, useMemo } from 'react'
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
import { useAnalyticsMastery } from '../../hooks/useApi'
import { useCourses } from '../../hooks/useApi'
import { LoadingSpinner } from '../ui'

export function MasteryBreakdown() {
  const [courseCode, setCourseCode] = useState<string>('')
  const { data: courses } = useCourses()
  const { data, isLoading, error } = useAnalyticsMastery(courseCode || undefined)

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

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-sm text-danger">Failed to load mastery data.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <h3 className="text-lg font-semibold text-text">Mastery by Week</h3>
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

      {isLoading && <LoadingSpinner label="Loading mastery data..." />}

      {!isLoading && chartData.length === 0 && (
        <div className="text-center py-12 text-text-muted text-sm">
          No flashcard data available yet. Upload lectures and generate flashcards to see mastery breakdown.
        </div>
      )}

      {!isLoading && chartData.length > 0 && (
        <div className="rounded-lg border border-border bg-surface p-4">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis
                dataKey="name"
                tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }}
                stroke="var(--color-border)"
              />
              <YAxis
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
                formatter={((value: number, name: string) => [value, name.charAt(0).toUpperCase() + name.slice(1)]) as never}
              />
              <Legend
                wrapperStyle={{ fontSize: 12, color: 'var(--color-text-muted)' }}
              />
              <Bar dataKey="mastered" stackId="a" fill="#22c55e" name="Mastered" radius={[0, 0, 0, 0]} />
              <Bar dataKey="learning" stackId="a" fill="#eab308" name="Learning" radius={[0, 0, 0, 0]} />
              <Bar dataKey="new" stackId="a" fill="#9ca3af" name="New" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>

          {/* Summary row */}
          <div className="flex items-center justify-center gap-6 mt-3 text-xs text-text-muted">
            <span>
              Total cards: {chartData.reduce((s, d) => s + d.total, 0)}
            </span>
            <span>
              Avg mastery: {chartData.length > 0 ? Math.round(chartData.reduce((s, d) => s + d.mastery_pct, 0) / chartData.length) : 0}%
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
