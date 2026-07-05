import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Modal, Select, toast } from '../ui'
import { toastMutationError } from '../../lib/toast'
import { useCourses, useMergeCourse } from '../../hooks/useApi'
import type { Course } from '../../types'

interface MergeCourseModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  course: Course
}

/**
 * Merge flow: pick a target course; colliding weeks become review items on
 * the backend instead of silent overwrites, and the source course is archived.
 */
export function MergeCourseModal({ open, onOpenChange, course }: MergeCourseModalProps) {
  const navigate = useNavigate()
  const [target, setTarget] = useState('')
  const [targetError, setTargetError] = useState<string | undefined>(undefined)
  const { data: courses } = useCourses()
  const mergeMutation = useMergeCourse()

  const options = (courses ?? [])
    .filter((c) => c.code !== course.code)
    .map((c) => ({ value: c.code, label: c.name ? `${c.code} — ${c.name}` : c.code }))

  const handleOpenChange = (next: boolean) => {
    if (!next) {
      setTarget('')
      setTargetError(undefined)
    }
    onOpenChange(next)
  }

  const handleMerge = () => {
    if (!target) {
      setTargetError('Pick a course to merge into')
      return
    }
    setTargetError(undefined)
    mergeMutation.mutate(
      { courseCode: course.code, into: target },
      {
        onSuccess: (result) => {
          const conflictNote =
            result.conflict_weeks.length > 0
              ? ` — ${result.conflict_weeks.length} colliding weeks sent to Review`
              : ''
          toast.success(`Merged ${course.code} into ${target}${conflictNote}`)
          navigate(`/courses/${target}`, { replace: true })
        },
        onError: (err) => toastMutationError(err, handleMerge),
      },
    )
  }

  return (
    <Modal
      open={open}
      onOpenChange={handleOpenChange}
      title={`Merge ${course.code} into another course`}
      description="All weeks, summaries and study assets move to the target. Colliding weeks create review items — nothing is overwritten. The source course is archived afterwards."
    >
      <div className="space-y-4">
        <Select
          id="merge-course-target"
          label="Merge into"
          options={options}
          value={target}
          onValueChange={setTarget}
          error={targetError}
          placeholder={options.length === 0 ? 'No other courses' : 'Select a course…'}
          disabled={options.length === 0}
        />
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" size="sm" onClick={() => handleOpenChange(false)}>
            Cancel
          </Button>
          <Button
            size="sm"
            disabled={!target}
            loading={mergeMutation.isPending}
            onClick={handleMerge}
          >
            Merge course
          </Button>
        </div>
      </div>
    </Modal>
  )
}
