import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useCourses, useCreateExam } from '../../hooks/useApi'
import { examCreateSchema, type ExamCreateFormData } from '../../lib/schemas'

interface ExamCreateFormProps {
  onClose: () => void
  onCreated?: () => void
}

export function ExamCreateForm({ onClose, onCreated }: ExamCreateFormProps) {
  const { data: courses } = useCourses()
  const createExam = useCreateExam()

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isValid },
  } = useForm<ExamCreateFormData>({
    resolver: zodResolver(examCreateSchema),
    defaultValues: { courseCode: '', title: '', examDate: '', weeksInput: '', targetMastery: 80 },
    mode: 'onChange',
  })

  const weeksInput = watch('weeksInput') // eslint-disable-line react-hooks/incompatible-library
  const targetMastery = watch('targetMastery')

  const parsedWeeks = (weeksInput || '')
    .split(',')
    .map((s) => parseInt(s.trim(), 10))
    .filter((n) => !isNaN(n) && n > 0)

  async function onSubmit(data: ExamCreateFormData) {
    const weeks = data.weeksInput
      .split(',')
      .map((s) => parseInt(s.trim(), 10))
      .filter((n) => !isNaN(n) && n > 0)

    await createExam.mutateAsync({
      course_code: data.courseCode,
      title: data.title,
      exam_date: new Date(data.examDate).toISOString(),
      weeks_scope: weeks,
      target_mastery_pct: data.targetMastery,
    })

    onCreated?.()
    onClose()
  }

  return (
    <div className="bg-surface-1 border border-border rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-text">Create Exam</h3>
        <button
          onClick={onClose}
          className="p-1.5 rounded-md text-text-muted hover:text-text hover:bg-surface-2 transition-colors"
        >
          {'\u2715'}
        </button>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-text mb-1">Course</label>
          <select
            {...register('courseCode')}
            className="w-full p-2.5 min-h-[44px] rounded-lg border border-border bg-surface-1 text-text text-sm focus:outline-none focus:ring-2 focus:ring-sage/30"
          >
            <option value="">Select a course</option>
            {courses?.map((c) => (
              <option key={c.id} value={c.code}>
                {c.code} {c.name ? `- ${c.name}` : ''}
              </option>
            ))}
          </select>
          {errors.courseCode && <p className="mt-1 text-xs text-red-fg">{errors.courseCode.message}</p>}
        </div>

        <div>
          <label className="block text-sm font-medium text-text mb-1">Exam Title</label>
          <input
            type="text"
            {...register('title')}
            placeholder="e.g., Midterm Exam"
            className="w-full p-2.5 min-h-[44px] rounded-lg border border-border bg-surface-1 text-text text-sm focus:outline-none focus:ring-2 focus:ring-sage/30"
          />
          {errors.title && <p className="mt-1 text-xs text-red-fg">{errors.title.message}</p>}
        </div>

        <div>
          <label className="block text-sm font-medium text-text mb-1">Exam Date</label>
          <input
            type="datetime-local"
            {...register('examDate')}
            className="w-full p-2.5 min-h-[44px] rounded-lg border border-border bg-surface-1 text-text text-sm focus:outline-none focus:ring-2 focus:ring-sage/30"
          />
          {errors.examDate && <p className="mt-1 text-xs text-red-fg">{errors.examDate.message}</p>}
        </div>

        <div>
          <label className="block text-sm font-medium text-text mb-1">
            Weeks Covered <span className="text-text-muted font-normal">(comma-separated)</span>
          </label>
          <input
            type="text"
            {...register('weeksInput')}
            placeholder="e.g., 1, 2, 3, 4, 5"
            className="w-full p-2.5 min-h-[44px] rounded-lg border border-border bg-surface-1 text-text text-sm focus:outline-none focus:ring-2 focus:ring-sage/30"
          />
          {errors.weeksInput && <p className="mt-1 text-xs text-red-fg">{errors.weeksInput.message}</p>}
          {parsedWeeks.length > 0 && (
            <div className="flex gap-1.5 mt-2 flex-wrap">
              {parsedWeeks.map((w) => (
                <span key={w} className="px-2 py-0.5 rounded-full bg-peri-soft text-peri-fg text-xs font-medium">
                  W{w}
                </span>
              ))}
            </div>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-text mb-1">
            Target Mastery: {targetMastery}%
          </label>
          <input
            type="range"
            min={50}
            max={100}
            step={5}
            {...register('targetMastery', { valueAsNumber: true })}
            className="w-full"
          />
        </div>

        <div className="flex gap-3 pt-2">
          <button
            type="submit"
            disabled={createExam.isPending || !isValid}
            className="flex-1 px-4 py-2.5 min-h-[44px] rounded-lg text-sm font-medium bg-sage text-on-accent hover:bg-sage-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {createExam.isPending ? 'Creating...' : 'Create Exam'}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2.5 min-h-[44px] rounded-lg text-sm font-medium bg-surface-0 text-text hover:bg-border transition-colors"
          >
            Cancel
          </button>
        </div>

        {createExam.isError && (
          <div className="p-3 rounded-lg bg-red-soft text-sm text-red-fg">
            {(createExam.error as Error).message || 'Failed to create exam'}
          </div>
        )}
      </form>
    </div>
  )
}
