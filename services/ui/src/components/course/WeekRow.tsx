import { Link, useNavigate } from 'react-router-dom'
import { StatusBadge, TCell, TRow } from '../ui'
import type { WeekSummaryRow } from '../../types'

interface WeekRowProps {
  courseCode: string
  week: WeekSummaryRow
}

const DONE_STATUSES = new Set(['completed', 'summarized', 'processed', 'generated'])

/** Dash shown for columns whose data source doesn't exist yet (due, quiz %, updated). */
function EmDash() {
  return <span className="text-text-faint">—</span>
}

/** One week as a dense table row per the course-page prototype. */
export function WeekRow({ courseCode, week }: WeekRowProps) {
  const navigate = useNavigate()
  const href = `/courses/${courseCode}/weeks/${week.week}`
  const title = week.titles.length > 0 ? week.titles.join(', ') : 'Untitled'

  return (
    <TRow onClick={() => navigate(href)}>
      <TCell className="pl-1 font-mono text-text-faint">
        {String(week.week).padStart(2, '0')}
      </TCell>
      <TCell className="font-medium">
        <span className="flex items-center gap-2">
          <Link
            to={href}
            className="text-text hover:text-sage-fg transition-colors"
            onClick={(e) => e.stopPropagation()}
          >
            {title}
          </Link>
          {!DONE_STATUSES.has(week.summary_status) && <StatusBadge status={week.summary_status} />}
        </span>
      </TCell>
      <TCell align="right" className="text-text-muted">
        {week.flashcard_count > 0 ? week.flashcard_count : <EmDash />}
      </TCell>
      <TCell align="right">
        <EmDash />
      </TCell>
      <TCell align="right">
        <EmDash />
      </TCell>
      <TCell align="right" className="pr-1">
        <EmDash />
      </TCell>
    </TRow>
  )
}
