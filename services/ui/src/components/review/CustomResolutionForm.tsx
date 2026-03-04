import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { customResolutionSchema, type CustomResolutionFormData } from '../../lib/schemas'

interface CustomResolutionFormProps {
  onSubmit: (resolution: Record<string, unknown>) => void
  isLoading: boolean
}

export function CustomResolutionForm({ onSubmit, isLoading }: CustomResolutionFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors, isValid },
  } = useForm<CustomResolutionFormData>({
    resolver: zodResolver(customResolutionSchema),
    defaultValues: { courseCode: '', weekNumber: '', title: '' },
    mode: 'onChange',
  })

  function onFormSubmit(data: CustomResolutionFormData) {
    const resolution: Record<string, unknown> = {}
    if (data.courseCode?.trim()) resolution.course_code = data.courseCode.trim()
    if (data.weekNumber?.trim()) resolution.week = Number(data.weekNumber)
    if (data.title?.trim()) resolution.title = data.title.trim()
    onSubmit(resolution)
  }

  return (
    <form onSubmit={handleSubmit(onFormSubmit)} className="space-y-3">
      <p className="text-xs font-medium text-text-muted uppercase tracking-wider">Manual Override</p>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div>
          <label htmlFor="course-code" className="block text-xs text-text-muted mb-1">Course Code</label>
          <input
            id="course-code"
            type="text"
            {...register('courseCode')}
            placeholder="e.g. CSIT302"
            className="w-full px-3 py-2.5 text-sm border border-border bg-surface text-text rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
          />
        </div>
        <div>
          <label htmlFor="week-num" className="block text-xs text-text-muted mb-1">Week Number</label>
          <input
            id="week-num"
            type="number"
            min={1}
            max={52}
            {...register('weekNumber')}
            placeholder="e.g. 3"
            className="w-full px-3 py-2.5 text-sm border border-border bg-surface text-text rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
          />
        </div>
        <div>
          <label htmlFor="title" className="block text-xs text-text-muted mb-1">Title</label>
          <input
            id="title"
            type="text"
            {...register('title')}
            placeholder="e.g. Data Structures"
            className="w-full px-3 py-2.5 text-sm border border-border bg-surface text-text rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
          />
        </div>
      </div>
      {errors.root && <p className="text-xs text-danger">{errors.root.message}</p>}
      <button
        type="submit"
        disabled={isLoading || !isValid}
        className="px-4 py-2.5 text-sm font-medium bg-primary text-white rounded-lg hover:bg-primary-dark disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {isLoading ? 'Resolving...' : 'Resolve with these values'}
      </button>
    </form>
  )
}
