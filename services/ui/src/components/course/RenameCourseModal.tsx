import { useState } from 'react'
import i18n from '../../i18n'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { Button, Input, Modal, toast } from '../ui'
import { toastMutationError } from '../../lib/toast'
import { useRenameCourse } from '../../hooks/useApi'
import type { Course } from '../../types'

interface RenameCourseModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  course: Course
}

/** Inline rename modal: course code + display name, wired to PATCH /api/courses/{code}. */
export function RenameCourseModal({ open, onOpenChange, course }: RenameCourseModalProps) {
  const { t } = useTranslation()

  const navigate = useNavigate()
  const [code, setCode] = useState(course.code)
  const [name, setName] = useState(course.name ?? '')
  const [codeError, setCodeError] = useState<string | undefined>(undefined)
  const renameMutation = useRenameCourse()

  const handleOpenChange = (next: boolean) => {
    if (!next) {
      setCode(course.code)
      setName(course.name ?? '')
      setCodeError(undefined)
    }
    onOpenChange(next)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmedCode = code.trim()
    if (!trimmedCode) {
      setCodeError('Course code is required')
      return
    }
    setCodeError(undefined)
    renameMutation.mutate(
      {
        courseCode: course.code,
        data: {
          new_code: trimmedCode !== course.code ? trimmedCode : undefined,
          name: name.trim() !== (course.name ?? '') ? name.trim() : undefined,
        },
      },
      {
        onSuccess: (updated) => {
          toast.success(i18n.t('Course renamed to {{code}}', { code: updated.code }))
          onOpenChange(false)
          if (updated.code !== course.code) {
            navigate(`/courses/${updated.code}`, { replace: true })
          }
        },
        onError: (err) => toastMutationError(err),
      },
    )
  }

  return (
    <Modal
      open={open}
      onOpenChange={handleOpenChange}
      title={t('Rename course')}
      description={t('Weeks, summaries and study assets follow the course automatically.')}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          id="rename-course-code"
          label={t('Course code')}
          value={code}
          error={codeError}
          maxLength={20}
          className="font-mono"
          onChange={(e) => setCode(e.target.value)}
        />
        <Input
          id="rename-course-name"
          label={t('Course name')}
          value={name}
          maxLength={255}
          placeholder={t('e.g. Cybersecurity')}
          onChange={(e) => setName(e.target.value)}
        />
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" size="sm" onClick={() => handleOpenChange(false)}>
            {t('Cancel')}
          </Button>
          <Button type="submit" size="sm" loading={renameMutation.isPending}>
            {t('Save')}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
