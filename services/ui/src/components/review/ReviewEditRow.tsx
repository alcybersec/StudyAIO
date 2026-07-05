import { useState } from 'react'
import { Button, Input, Select } from '../ui'
import { itemGuess } from './reviewUtils'
import type { CourseListItem, ReviewItem } from '../../types'

interface ReviewEditRowProps {
  item: ReviewItem
  courses: CourseListItem[]
  busy: boolean
  onConfirm: (resolution: Record<string, unknown>) => void
  onCancel: () => void
}

function parseWeek(raw: string): number | null {
  if (!/^\d+$/.test(raw)) return null
  const week = Number(raw)
  return week >= 1 && week <= 52 ? week : null
}

/** Inline course/week correction shown under a focused review row. */
export function ReviewEditRow({ item, courses, busy, onConfirm, onCancel }: ReviewEditRowProps) {
  const guess = itemGuess(item)
  const [courseCode, setCourseCode] = useState(
    guess.courseCode && guess.courseCode !== 'UNKNOWN' ? guess.courseCode : '',
  )
  const [week, setWeek] = useState(guess.week !== null ? String(guess.week) : '')

  const weekInvalid = week.trim() !== '' && parseWeek(week.trim()) === null
  const canConfirm = courseCode !== '' && !weekInvalid && !busy

  const options = courses.map((course) => ({
    value: course.code,
    label: course.name ? `${course.code} — ${course.name}` : course.code,
  }))

  const confirm = () => {
    if (!canConfirm) return
    const resolution: Record<string, unknown> = { course_code: courseCode }
    const parsedWeek = parseWeek(week.trim())
    if (parsedWeek !== null) resolution.week = parsedWeek
    if (guess.title !== null) resolution.title = guess.title
    onConfirm(resolution)
  }

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter') {
      event.preventDefault()
      confirm()
    } else if (event.key === 'Escape') {
      event.preventDefault()
      onCancel()
    }
  }

  return (
    <div
      className="mt-2.5 ml-7 bg-surface-0 border border-border rounded-lg p-3 flex items-end gap-3 flex-wrap"
      onKeyDown={handleKeyDown}
    >
      <Select
        label="Course"
        options={options}
        value={courseCode || undefined}
        onValueChange={setCourseCode}
        placeholder="Pick a course…"
        disabled={busy}
        className="w-52"
      />
      <Input
        label="Week"
        id={`week-${item.id}`}
        value={week}
        onChange={(event) => setWeek(event.target.value)}
        error={weekInvalid ? '1–52' : undefined}
        inputMode="numeric"
        disabled={busy}
        className="w-20"
      />
      <div className="flex items-center gap-1.5 pb-0.5">
        <Button size="sm" kbd="↵" onClick={confirm} disabled={!canConfirm} loading={busy}>
          Confirm
        </Button>
        <Button variant="ghost" size="sm" kbd="esc" onClick={onCancel} disabled={busy}>
          Cancel
        </Button>
      </div>
    </div>
  )
}
