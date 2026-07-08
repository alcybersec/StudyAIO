import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as Dialog from '@radix-ui/react-dialog'
import { useCreateAssessment } from '../../hooks/useApi'
import { assessmentCreateSchema, type AssessmentCreateFormData } from '../../lib/schemas'

const FIELD =
  'mt-1 w-full rounded-md border border-border bg-surface-1 text-text px-3 py-2 text-sm focus:border-sage focus:outline-none focus:ring-1 focus:ring-sage'

interface AddAssessmentModalProps {
  courseCode: string
  onClose: () => void
}

export function AddAssessmentModal({ courseCode, onClose }: AddAssessmentModalProps) {
  const createAssessment = useCreateAssessment(courseCode)

  const {
    register,
    handleSubmit,
    formState: { errors, isValid },
  } = useForm<AssessmentCreateFormData>({
    resolver: zodResolver(assessmentCreateSchema),
    defaultValues: { title: '', assessmentType: 'exam', weightPct: '', description: '' },
    mode: 'onChange',
  })

  function onSubmit(data: AssessmentCreateFormData) {
    const weight = data.weightPct === '' || data.weightPct === undefined ? null : Number(data.weightPct)
    createAssessment.mutate(
      {
        title: data.title,
        assessment_type: data.assessmentType,
        weight_pct: weight,
        description: data.description || null,
      },
      { onSuccess: onClose },
    )
  }

  return (
    <Dialog.Root open onOpenChange={(open) => !open && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/50" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2 mx-4 w-full max-w-md rounded-lg bg-surface-1 border border-border p-6 shadow-xl focus:outline-none">
          <Dialog.Title className="mb-4 text-lg font-medium text-text">Add assessment</Dialog.Title>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-text">Title</label>
              <input type="text" autoFocus placeholder="e.g. Final Exam" {...register('title')} className={FIELD} />
              {errors.title && <p className="mt-1 text-xs text-red-fg">{errors.title.message}</p>}
            </div>

            <div>
              <label className="block text-sm font-medium text-text">Type</label>
              <select {...register('assessmentType')} className={FIELD}>
                {['exam', 'assignment', 'quiz', 'project', 'lab', 'presentation', 'other'].map((t) => (
                  <option key={t} value={t}>
                    {t.charAt(0).toUpperCase() + t.slice(1)}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-text">Weight % (optional)</label>
              <input
                type="number"
                min={0}
                max={100}
                step="any"
                placeholder="e.g. 40"
                {...register('weightPct')}
                className={FIELD}
              />
              {errors.weightPct && <p className="mt-1 text-xs text-red-fg">{errors.weightPct.message}</p>}
            </div>

            <div>
              <label className="block text-sm font-medium text-text">Description (optional)</label>
              <textarea {...register('description')} rows={2} className={FIELD} />
            </div>

            {createAssessment.isError && (
              <p className="text-xs text-red-fg" role="alert">
                Couldn't add the assessment. Please try again.
              </p>
            )}

            <div className="mt-5 flex justify-end gap-2">
              <Dialog.Close asChild>
                <button
                  type="button"
                  className="rounded-md border border-border px-4 py-2 text-sm text-text hover:bg-surface-2"
                >
                  Cancel
                </button>
              </Dialog.Close>
              <button
                type="submit"
                disabled={createAssessment.isPending || !isValid}
                className="rounded-md bg-sage px-4 py-2 text-sm text-on-accent hover:bg-sage-hover disabled:opacity-50"
              >
                {createAssessment.isPending ? 'Adding…' : 'Add assessment'}
              </button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
