import { useMemo } from 'react'
import { Card, EmptyState, ErrorState, SectionLabel, Skeleton } from '../ui'
import { useAnalyticsHeatmap } from '../../hooks/useApi'
import { heatLevel, LEVEL_OPACITY } from './trend'

const DAY_LABELS = ['', 'Mon', '', 'Wed', '', 'Fri', '']
const CELL_SIZE = 12
const CELL_GAP = 3
const LABEL_WIDTH = 32
const WEEKS = 13

function getMonthLabels(days: { date: string }[]): { label: string; col: number }[] {
  const labels: { label: string; col: number }[] = []
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  let lastMonth = -1

  for (let i = 0; i < days.length; i++) {
    if (!days[i].date) continue
    const d = new Date(days[i].date)
    const month = d.getMonth()
    if (month !== lastMonth) {
      labels.push({ label: months[month], col: Math.floor(i / 7) })
      lastMonth = month
    }
  }
  return labels
}

export function StudyHeatmap() {
  const { data, isLoading, error, refetch } = useAnalyticsHeatmap(91)

  const grid = useMemo(() => {
    if (!data?.days) return []
    const days = data.days.slice(-91)
    const padCount = WEEKS * 7 - days.length
    return [
      ...Array.from({ length: padCount }, () => ({ date: '', minutes: 0, cards: 0, sessions: 0 })),
      ...days,
    ]
  }, [data])

  const monthLabels = useMemo(() => getMonthLabels(grid), [grid])

  const hasActivity = useMemo(() => grid.some((d) => d.minutes > 0), [grid])

  if (isLoading) {
    return (
      <Card padding>
        <Skeleton height={12} width={96} className="mb-3" />
        <Skeleton height={110} width="100%" />
      </Card>
    )
  }

  if (error) {
    return (
      <ErrorState
        title="Study heatmap couldn't load"
        detail={error instanceof Error ? error.message : undefined}
        onRetry={() => refetch()}
      />
    )
  }

  if (!data?.days || data.days.length === 0 || !hasActivity) {
    return (
      <Card>
        <EmptyState
          icon="🗓"
          title="No study activity yet"
          description="No sessions in the last 90 days. Study a few cards and the grid starts filling in."
          actionLabel="Start a session"
          actionTo="/study?tab=flashcards"
        />
      </Card>
    )
  }

  const svgWidth = LABEL_WIDTH + WEEKS * (CELL_SIZE + CELL_GAP)
  const svgHeight = 20 + 7 * (CELL_SIZE + CELL_GAP) + 4

  return (
    <Card padding>
      <SectionLabel>Study heatmap</SectionLabel>
      <div className="overflow-x-auto">
        <svg
          width={svgWidth}
          height={svgHeight}
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          className="block"
          role="img"
          aria-label="Study activity heatmap — last 13 weeks"
        >
          {monthLabels.map(({ label, col }, i) => (
            <text
              key={`m-${i}`}
              x={LABEL_WIDTH + col * (CELL_SIZE + CELL_GAP)}
              y={12}
              className="font-mono"
              fontSize={10}
              fill="var(--t-text-faint)"
            >
              {label}
            </text>
          ))}

          {DAY_LABELS.map((label, row) =>
            label ? (
              <text
                key={`d-${row}`}
                x={0}
                y={22 + row * (CELL_SIZE + CELL_GAP) + CELL_SIZE - 2}
                className="font-mono"
                fontSize={10}
                fill="var(--t-text-faint)"
              >
                {label}
              </text>
            ) : null,
          )}

          {grid.map((day, i) => {
            const col = Math.floor(i / 7)
            const row = i % 7
            const x = LABEL_WIDTH + col * (CELL_SIZE + CELL_GAP)
            const y = 20 + row * (CELL_SIZE + CELL_GAP)
            const level = heatLevel(day.minutes)
            const tooltip = day.date ? `${day.date}: ${day.minutes}min, ${day.cards} cards` : ''

            return (
              <rect
                key={i}
                x={x}
                y={y}
                width={CELL_SIZE}
                height={CELL_SIZE}
                rx={3}
                style={
                  level === 0
                    ? { fill: 'var(--t-surface-2)' }
                    : { fill: 'var(--t-sage)', opacity: LEVEL_OPACITY[level] }
                }
              >
                {tooltip && <title>{tooltip}</title>}
              </rect>
            )
          })}
        </svg>
      </div>

      <div className="flex items-center gap-1.5 mt-2.5 font-mono text-[10px] text-text-faint">
        less
        <span
          className="inline-block rounded-[3px]"
          style={{ width: CELL_SIZE, height: CELL_SIZE, background: 'var(--t-surface-2)' }}
        />
        {LEVEL_OPACITY.slice(1).map((o) => (
          <span
            key={o}
            className="inline-block rounded-[3px]"
            style={{ width: CELL_SIZE, height: CELL_SIZE, background: 'var(--t-sage)', opacity: o }}
          />
        ))}
        more
      </div>
    </Card>
  )
}
