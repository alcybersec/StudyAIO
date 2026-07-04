import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, Archive } from 'lucide-react'
import { Button, Input, Modal, toast } from '../ui'
import { toastMutationError } from '../../lib/toast'
import { useArchiveCourse, useDeleteCourse } from '../../hooks/useApi'
import type { Course, WeekSummaryRow } from '../../types'

interface DeleteCourseModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  course: Course
  weeks: WeekSummaryRow[]
}

/**
 * Type-to-confirm delete flow per the course-page prototype: consequences
 * built from real course stats, danger button gated on the typed code, and
 * an "Archive instead" escape hatch that keeps everything recoverable.
 */
export function DeleteCourseModal({ open, onOpenChange, course, weeks }: DeleteCourseModalProps) {
  const navigate = useNavigate()
  const [typed, setTyped] = useState('')
  const deleteMutation = useDeleteCourse()
  const archiveMutation = useArchiveCourse()

  const stats = useMemo(
    () => ({
      weeks: weeks.length,
      flashcards: weeks.reduce((sum, w) => sum + w.flashcard_count, 0),
      quizzes: weeks.reduce((sum, w) => sum + w.quiz_count, 0),
      files: weeks.reduce((sum, w) => sum + w.artifact_count, 0),
    }),
    [weeks],
  )

  const handleOpenChange = (next: boolean) => {
    if (!next) setTyped('')
    onOpenChange(next)
  }

  const handleDelete = () => {
    deleteMutation.mutate(course.code, {
      onSuccess: () => {
        toast.success(`${course.code} deleted`)
        navigate('/')
      },
      onError: (err) => toastMutationError(err, handleDelete),
    })
  }

  const handleArchive = () => {
    archiveMutation.mutate(course.code, {
      onSuccess: () => {
        toast.success(`${course.code} archived — recoverable anytime`)
        navigate('/')
      },
      onError: (err) => toastMutationError(err, handleArchive),
    })
  }

  return (
    <Modal
      open={open}
      onOpenChange={handleOpenChange}
      title={
        <span className="flex items-center gap-2.5">
          <span className="w-8 h-8 rounded-lg bg-red-soft text-red-fg flex items-center justify-center shrink-0">
            <AlertTriangle size={15} aria-hidden />
          </span>
          Delete {course.code}
          {course.name ? ` — ${course.name}` : ''}?
        </span>
      }
      description="This can't be undone. Archiving keeps everything recoverable."
      className="border-red/30"
    >
      <ul className="text-xs text-text-muted space-y-1 mb-4 ml-1">
        <li>· {stats.weeks} weeks of summaries</li>
        <li>· {stats.flashcards} flashcards with review history</li>
        <li>· {stats.quizzes} quiz questions</li>
        <li>· {stats.files} uploaded source files stay in storage until purged</li>
      </ul>
      <Input
        id="delete-course-confirm"
        label={`Type "${course.code}" to confirm`}
        placeholder={course.code}
        value={typed}
        autoComplete="off"
        onChange={(e) => setTyped(e.target.value)}
      />
      <div className="flex flex-wrap justify-end gap-2 mt-4">
        <Button variant="secondary" size="sm" onClick={() => handleOpenChange(false)}>
          Cancel
        </Button>
        <Button
          variant="secondary"
          size="sm"
          loading={archiveMutation.isPending}
          onClick={handleArchive}
        >
          <Archive size={12} aria-hidden /> Archive instead
        </Button>
        <Button
          variant="danger"
          size="sm"
          disabled={typed !== course.code}
          loading={deleteMutation.isPending}
          onClick={handleDelete}
        >
          Delete permanently
        </Button>
      </div>
    </Modal>
  )
}
