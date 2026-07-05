import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FolderInput, X } from 'lucide-react'
import { Badge, Button, Card, Input, Select, toast } from '../ui'
import { useCourses, useReclassifyArtifact } from '../../hooks/useApi'
import { toastMutationError } from '../../lib/toast'
import type { Artifact } from '../../types'

interface ReclassifyPanelProps {
  artifact: Artifact
  courseCode: string
  week: number
  onClose: () => void
}

const MIN_WEEK = 0
const MAX_WEEK = 52

export function ReclassifyPanel({ artifact, courseCode, week, onClose }: ReclassifyPanelProps) {
  const navigate = useNavigate()
  const { data: courses, isLoading: coursesLoading } = useCourses()
  const reclassify = useReclassifyArtifact()
  const [targetCourse, setTargetCourse] = useState(courseCode)
  const [weekInput, setWeekInput] = useState(String(week))

  const parsedWeek = /^\d+$/.test(weekInput.trim()) ? Number(weekInput.trim()) : null
  const weekValid = parsedWeek !== null && parsedWeek >= MIN_WEEK && parsedWeek <= MAX_WEEK
  const unchanged = targetCourse === courseCode && parsedWeek === week

  const move = () => {
    if (!weekValid || parsedWeek === null) return
    reclassify.mutate(
      { artifactId: artifact.id, courseCode: targetCourse, week: parsedWeek },
      {
        onSuccess: () => {
          toast.success(`Moved to ${targetCourse} week ${parsedWeek}`, {
            action: {
              label: 'Open',
              onClick: () => navigate(`/courses/${targetCourse}/weeks/${parsedWeek}`),
            },
          })
          onClose()
        },
        onError: (err) => toastMutationError(err, move),
      },
    )
  }

  return (
    <Card className="mb-4 border-peri/30">
      <div className="flex items-start justify-between mb-3">
        <div>
          <p className="text-sm font-semibold text-text flex items-center gap-2">
            <FolderInput size={14} className="text-peri-fg" aria-hidden /> Reclassify this week's material
          </p>
          <p className="text-xs text-text-muted mt-1">
            Applies to <span className="font-mono">{artifact.original_filename}</span> — currently{' '}
            <Badge>
              {courseCode} · Week {week}
            </Badge>
          </p>
        </div>
        <button
          onClick={onClose}
          className="text-text-faint hover:text-text-muted cursor-pointer p-1"
          aria-label="Close reclassify panel"
        >
          <X size={14} aria-hidden />
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-[1fr_120px_auto] gap-3 items-end max-w-lg">
        <Select
          label="Move to course"
          options={(courses ?? []).map((c) => ({
            value: c.code,
            label: c.name ? `${c.code} — ${c.name}` : c.code,
          }))}
          value={targetCourse}
          onValueChange={setTargetCourse}
          disabled={coursesLoading}
          placeholder={coursesLoading ? 'Loading courses…' : 'Select course'}
        />
        <Input
          label="Week"
          inputMode="numeric"
          value={weekInput}
          onChange={(e) => setWeekInput(e.target.value)}
          error={weekInput !== '' && !weekValid ? `0–${MAX_WEEK}` : undefined}
        />
        <div className="flex gap-2">
          <Button size="md" onClick={move} loading={reclassify.isPending} disabled={!weekValid || unchanged}>
            Move
          </Button>
          <Button size="md" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
        </div>
      </div>

      <p className="text-[11px] text-text-faint mt-3">
        The summary, flashcards and quiz move with the file. If the destination week already has a summary, it's
        re-generated as a new version merging both sources — nothing is overwritten silently.
      </p>
    </Card>
  )
}
