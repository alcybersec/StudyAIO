import { useRef, type KeyboardEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Check, CircleDashed, Minus, TriangleAlert } from 'lucide-react'
import {
  MASTERY_CELL_CLASS,
  MASTERY_STATES,
  masteryLabel,
  masteryState,
  type MasteryState,
} from '../../lib/weakSpots'
import type { WeakSpotCourse, WeakSpotWeek } from '../../types'
import { Tooltip } from '../ui'

export interface HeatmapSelection {
  courseId: string
  week: number
}

interface MasteryHeatmapProps {
  courses: WeakSpotCourse[]
  selected: HeatmapSelection | null
  onSelect: (selection: HeatmapSelection) => void
}

const STATE_ICON: Record<MasteryState, typeof Check> = {
  unknown: CircleDashed,
  weak: TriangleAlert,
  ok: Minus,
  solid: Check,
}

function cellDescription(
  t: (key: string, opts?: Record<string, unknown>) => string,
  course: WeakSpotCourse,
  w: WeakSpotWeek,
): string {
  const state = masteryLabel(masteryState(w.status))
  const parts = [t('{{course}} week {{week}}: {{state}}', { course: course.course_code, week: w.week, state })]
  if (w.weakness != null) parts.push(t('weakness {{pct}}%', { pct: Math.round(w.weakness * 100) }))
  if (masteryState(w.status) === 'unknown') {
    parts.push(t('answer a few questions or cards to see how this week is going'))
  }
  if (w.next_exam) parts.push(t('exam in {{days}}d', { days: w.next_exam.days_to_exam }))
  return parts.join(', ')
}

/** Legend with a text label per state, so colour is never the only signal. */
export function MasteryLegend() {
  const { t } = useTranslation()
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1.5" aria-label={t('Legend')}>
      {MASTERY_STATES.map((s) => {
        const Icon = STATE_ICON[s]
        return (
          <li key={s} className="flex items-center gap-1.5 text-xs text-text-muted">
            <span
              className={`inline-flex h-5 w-5 items-center justify-center rounded border ${MASTERY_CELL_CLASS[s]}`}
              aria-hidden
            >
              <Icon size={11} />
            </span>
            {masteryLabel(s)}
          </li>
        )
      })}
    </ul>
  )
}

/**
 * Course x week mastery map. One focusable cell at a time (roving tabindex);
 * arrow keys move within a course, up/down between courses. Unknown weeks are a
 * neutral dashed cell: lack of evidence is not a weakness.
 */
export function MasteryHeatmap({ courses, selected, onSelect }: MasteryHeatmapProps) {
  const { t } = useTranslation()
  const refs = useRef<Map<string, HTMLButtonElement>>(new Map())
  const key = (ci: number, wi: number) => `${ci}:${wi}`

  const firstKey =
    selected != null
      ? (() => {
          const ci = courses.findIndex((c) => c.course_id === selected.courseId)
          const wi = ci >= 0 ? courses[ci].weeks.findIndex((w) => w.week === selected.week) : -1
          return wi >= 0 ? key(ci, wi) : key(0, 0)
        })()
      : key(0, 0)

  const move = (ci: number, wi: number, e: KeyboardEvent) => {
    let nci = ci
    let nwi = wi
    switch (e.key) {
      case 'ArrowRight':
        nwi = Math.min(wi + 1, courses[ci].weeks.length - 1)
        break
      case 'ArrowLeft':
        nwi = Math.max(wi - 1, 0)
        break
      case 'ArrowDown':
        nci = Math.min(ci + 1, courses.length - 1)
        nwi = Math.min(wi, courses[nci].weeks.length - 1)
        break
      case 'ArrowUp':
        nci = Math.max(ci - 1, 0)
        nwi = Math.min(wi, courses[nci].weeks.length - 1)
        break
      case 'Home':
        nwi = 0
        break
      case 'End':
        nwi = courses[ci].weeks.length - 1
        break
      default:
        return
    }
    e.preventDefault()
    if (nwi < 0) return
    refs.current.get(key(nci, nwi))?.focus()
  }

  return (
    <div role="grid" aria-label={t('Mastery by course and week')} className="space-y-3">
      {courses.map((course, ci) => (
        <div key={course.course_id} role="row" className="flex flex-col gap-1.5 sm:flex-row sm:items-center sm:gap-3">
          <span role="rowheader" className="font-mono text-xs text-text-muted sm:w-24 sm:shrink-0">
            {course.course_code}
          </span>
          <div className="flex flex-wrap gap-1.5">
            {course.weeks.map((w, wi) => {
              const state = masteryState(w.status)
              const Icon = STATE_ICON[state]
              const isSelected = selected?.courseId === course.course_id && selected.week === w.week
              const k = key(ci, wi)
              const description = cellDescription(t, course, w)
              return (
                <div key={w.week} role="gridcell">
                  <Tooltip content={description}>
                    <button
                      type="button"
                      ref={(el) => {
                        if (el) refs.current.set(k, el)
                        else refs.current.delete(k)
                      }}
                      tabIndex={k === firstKey ? 0 : -1}
                      aria-label={description}
                      aria-pressed={isSelected}
                      data-state={state}
                      onClick={() => onSelect({ courseId: course.course_id, week: w.week })}
                      onKeyDown={(e) => move(ci, wi, e)}
                      className={`flex h-11 w-11 cursor-pointer flex-col items-center justify-center rounded-md border text-[11px] font-medium leading-none transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-peri ${MASTERY_CELL_CLASS[state]} ${isSelected ? 'ring-2 ring-peri' : ''}`}
                    >
                      <Icon size={11} aria-hidden />
                      <span className="mt-0.5 tabular-nums">{w.week}</span>
                    </button>
                  </Tooltip>
                </div>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}
