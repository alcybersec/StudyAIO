import { useMemo } from 'react'
import { useAnalyticsHeatmap } from '../../hooks/useApi'
import { LoadingSpinner } from '../ui'

const DAY_LABELS = ['', 'Mon', '', 'Wed', '', 'Fri', '']
const CELL_SIZE = 14
const CELL_GAP = 3
const LABEL_WIDTH = 32
const WEEKS = 13

function getColorClass(minutes: number, isDark: boolean): string {
  if (minutes === 0) return isDark ? 'fill-gray-800' : 'fill-gray-100'
  if (minutes <= 15) return isDark ? 'fill-emerald-900' : 'fill-green-200'
  if (minutes <= 30) return isDark ? 'fill-emerald-700' : 'fill-green-400'
  if (minutes <= 60) return isDark ? 'fill-emerald-500' : 'fill-green-500'
  return isDark ? 'fill-teal-400' : 'fill-green-700'
}

function getMonthLabels(days: { date: string }[]): { label: string; col: number }[] {
  const labels: { label: string; col: number }[] = []
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  let lastMonth = -1

  for (let i = 0; i < days.length; i++) {
    const d = new Date(days[i].date)
    const month = d.getMonth()
    if (month !== lastMonth) {
      const col = Math.floor(i / 7)
      labels.push({ label: months[month], col })
      lastMonth = month
    }
  }
  return labels
}

export function StudyHeatmap() {
  const { data, isLoading, error } = useAnalyticsHeatmap(91)

  const isDark = useMemo(() => {
    if (typeof document === 'undefined') return false
    return document.documentElement.classList.contains('dark')
  }, [])

  const grid = useMemo(() => {
    if (!data?.days) return []
    // Pad to full weeks (13 weeks = 91 days)
    const days = data.days.slice(-91)
    // Pad from the start so the grid fills 13 columns
    const padCount = WEEKS * 7 - days.length
    const padded = [
      ...Array.from({ length: padCount }, () => ({ date: '', minutes: 0, cards: 0, sessions: 0 })),
      ...days,
    ]
    return padded
  }, [data])

  const monthLabels = useMemo(() => {
    if (!data?.days) return []
    const days = data.days.slice(-91)
    const padCount = WEEKS * 7 - days.length
    const padded = [
      ...Array.from({ length: padCount }, () => ({ date: '' })),
      ...days,
    ]
    return getMonthLabels(padded.filter((d) => d.date))
  }, [data])

  if (isLoading) return <LoadingSpinner label="Loading heatmap..." />

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-sm text-danger">Failed to load heatmap data.</p>
      </div>
    )
  }

  if (!data?.days || data.days.length === 0) {
    return (
      <div className="text-center py-12 text-text-muted text-sm">
        No study activity in the last 90 days. Start studying to build your heatmap.
      </div>
    )
  }

  const svgWidth = LABEL_WIDTH + WEEKS * (CELL_SIZE + CELL_GAP)
  const svgHeight = 20 + 7 * (CELL_SIZE + CELL_GAP) + 30

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-text">Study Activity</h3>
      <div className="overflow-x-auto">
        <svg
          width={svgWidth}
          height={svgHeight}
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          className="block"
          role="img"
          aria-label="Study activity heatmap"
        >
          {/* Month labels */}
          {monthLabels.map(({ label, col }, i) => (
            <text
              key={`m-${i}`}
              x={LABEL_WIDTH + col * (CELL_SIZE + CELL_GAP)}
              y={12}
              className="fill-text-muted text-[10px]"
              fontSize={10}
            >
              {label}
            </text>
          ))}

          {/* Day labels */}
          {DAY_LABELS.map((label, row) =>
            label ? (
              <text
                key={`d-${row}`}
                x={0}
                y={22 + row * (CELL_SIZE + CELL_GAP) + CELL_SIZE - 2}
                className="fill-text-muted text-[10px]"
                fontSize={10}
              >
                {label}
              </text>
            ) : null,
          )}

          {/* Cells */}
          {grid.map((day, i) => {
            const col = Math.floor(i / 7)
            const row = i % 7
            const x = LABEL_WIDTH + col * (CELL_SIZE + CELL_GAP)
            const y = 20 + row * (CELL_SIZE + CELL_GAP)
            const tooltip = day.date
              ? `${day.date}: ${day.minutes}min, ${day.cards} cards`
              : ''

            return (
              <rect
                key={i}
                x={x}
                y={y}
                width={CELL_SIZE}
                height={CELL_SIZE}
                rx={2}
                className={`${getColorClass(day.minutes, isDark)} transition-colors`}
              >
                {tooltip && <title>{tooltip}</title>}
              </rect>
            )
          })}
        </svg>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-2 text-xs text-text-muted">
        <span>Less</span>
        {[0, 15, 30, 60, 90].map((min) => (
          <svg key={min} width={CELL_SIZE} height={CELL_SIZE}>
            <rect
              width={CELL_SIZE}
              height={CELL_SIZE}
              rx={2}
              className={getColorClass(min, isDark)}
            />
          </svg>
        ))}
        <span>More</span>
      </div>
    </div>
  )
}
