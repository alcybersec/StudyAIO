import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as Dialog from '@radix-ui/react-dialog'
import { useUpdateDeadline } from '../../hooks/useApi'
import { deadlineEditSchema, type DeadlineEditFormData } from '../../lib/schemas'
import type { Deadline } from '../../types'

interface DeadlineEditModalProps {
  deadline: Deadline
  onClose: () => void
}

export function DeadlineEditModal({ deadline, onClose }: DeadlineEditModalProps) {
  const updateDeadline = useUpdateDeadline()

  const {
    register,
    handleSubmit,
    formState: { errors, isValid },
  } = useForm<DeadlineEditFormData>({
    resolver: zodResolver(deadlineEditSchema),
    defaultValues: {
      title: deadline.title,
      dueDate: deadline.due_date,
      deadlineType: deadline.deadline_type,
      description: deadline.description ?? '',
    },
    mode: 'onChange',
  })

  function onSubmit(data: DeadlineEditFormData) {
    updateDeadline.mutate(
      {
        deadlineId: deadline.id,
        data: {
          title: data.title,
          due_date: data.dueDate,
          deadline_type: data.deadlineType,
          description: data.description || undefined,
          is_confirmed: true,
        },
      },
      { onSuccess: onClose }
    )
  }

  return (
    <Dialog.Root open onOpenChange={(open) => !open && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/50" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2 mx-4 w-full max-w-md rounded-lg bg-surface border border-border p-6 shadow-xl focus:outline-none">
          <Dialog.Title className="mb-4 text-lg font-medium text-text">Edit Deadline</Dialog.Title>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-text">Title</label>
              <input
                type="text"
                {...register('title')}
                className="mt-1 w-full rounded-md border border-border bg-surface text-text px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              />
              {errors.title && <p className="mt-1 text-xs text-danger">{errors.title.message}</p>}
            </div>

            <div>
              <label className="block text-sm font-medium text-text">Due Date</label>
              <input
                type="date"
                {...register('dueDate')}
                className="mt-1 w-full rounded-md border border-border bg-surface text-text px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              />
              {errors.dueDate && <p className="mt-1 text-xs text-danger">{errors.dueDate.message}</p>}
            </div>

            <div>
              <label className="block text-sm font-medium text-text">Type</label>
              <select
                {...register('deadlineType')}
                className="mt-1 w-full rounded-md border border-border bg-surface text-text px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              >
                {['exam', 'assignment', 'quiz', 'project', 'lab', 'presentation', 'other'].map((t) => (
                  <option key={t} value={t}>
                    {t.charAt(0).toUpperCase() + t.slice(1)}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-text">Description</label>
              <textarea
                {...register('description')}
                rows={2}
                className="mt-1 w-full rounded-md border border-border bg-surface text-text px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>

            <div className="mt-5 flex justify-end gap-2">
              <Dialog.Close asChild>
                <button
                  type="button"
                  className="rounded-md border border-border px-4 py-2 text-sm text-text hover:bg-surface-alt"
                >
                  Cancel
                </button>
              </Dialog.Close>
              <button
                type="submit"
                disabled={updateDeadline.isPending || !isValid}
                className="rounded-md bg-primary px-4 py-2 text-sm text-white hover:bg-primary-dark disabled:opacity-50"
              >
                {updateDeadline.isPending ? 'Saving...' : 'Save & Confirm'}
              </button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
