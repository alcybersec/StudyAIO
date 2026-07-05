import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Card, ErrorState, Input, SkeletonCard } from '../../ui'
import { FieldSavedNote } from '../FieldSavedNote'
import { useSavedFields } from '../useSavedFields'
import { useSettings, useUpdateSettings } from '../../../hooks/useApi'
import { toastMutationError } from '../../../lib/toast'
import { pipelineSettingsSchema, type PipelineSettingsFormData } from '../../../lib/schemas'
import type { Settings } from '../../../types'

interface FieldMeta {
  name: keyof PipelineSettingsFormData
  label: string
  hint: string
  min: number
  max: number
}

const FIELDS: FieldMeta[] = [
  {
    name: 'flashcard_count_per_week',
    label: 'Flashcards per week',
    hint: 'Number of flashcards generated per lecture (1–100)',
    min: 1,
    max: 100,
  },
  {
    name: 'quiz_question_count_per_week',
    label: 'Quiz questions per week',
    hint: 'Number of quiz questions generated per lecture (1–100)',
    min: 1,
    max: 100,
  },
  {
    name: 'chunk_size_tokens',
    label: 'Chunk size (tokens)',
    hint: 'Token window size for text chunking in the index stage (50–5000)',
    min: 50,
    max: 5000,
  },
  {
    name: 'chunk_overlap_tokens',
    label: 'Chunk overlap (tokens)',
    hint: 'Overlap between consecutive chunks (0–500)',
    min: 0,
    max: 500,
  },
]

function toFormValues(s: Settings): PipelineSettingsFormData {
  return {
    flashcard_count_per_week: s.flashcard_count_per_week,
    quiz_question_count_per_week: s.quiz_question_count_per_week,
    chunk_size_tokens: s.chunk_size_tokens,
    chunk_overlap_tokens: s.chunk_overlap_tokens,
  }
}

export function PipelineSection() {
  const { data: settings, isLoading, error, refetch } = useSettings()

  if (isLoading) return <SkeletonCard />
  if (error) {
    return (
      <ErrorState
        title="Pipeline settings couldn't load"
        detail={error instanceof Error ? error.message : undefined}
        onRetry={() => refetch()}
      />
    )
  }
  if (!settings) return null

  return <PipelineForm settings={settings} />
}

function PipelineForm({ settings }: { settings: Settings }) {
  const updateMutation = useUpdateSettings()
  const { saved, markSaved } = useSavedFields()

  const {
    register,
    getValues,
    trigger,
    formState: { errors },
  } = useForm<PipelineSettingsFormData>({
    resolver: zodResolver(pipelineSettingsSchema),
    mode: 'onBlur',
    values: toFormValues(settings),
    resetOptions: { keepDirtyValues: true },
  })

  const saveField = async (field: keyof PipelineSettingsFormData) => {
    const valid = await trigger(field)
    if (!valid) return
    const value = getValues(field)
    if (toFormValues(settings)[field] === value) return
    updateMutation.mutate(
      { [field]: value },
      {
        onSuccess: () => markSaved(field),
        onError: (err) => toastMutationError(err),
      },
    )
  }

  return (
    <Card>
      <h2 className="text-[13px] font-semibold text-text mb-4">Pipeline tuning</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {FIELDS.map(({ name, label, hint, min, max }) => (
          <div key={name}>
            <div className="flex items-center justify-between mb-1.5">
              <label htmlFor={name} className="text-xs font-medium text-text-muted">
                {label}
              </label>
              <FieldSavedNote show={!!saved[name]} />
            </div>
            <Input
              id={name}
              type="number"
              min={min}
              max={max}
              error={errors[name]?.message}
              {...register(name, { valueAsNumber: true, onBlur: () => saveField(name) })}
            />
            <p className="mt-1.5 text-xs text-text-faint">{hint}</p>
          </div>
        ))}
      </div>
      <div className="flex items-center justify-between mt-5 pt-3 border-t border-border">
        <span className="text-xs text-text-faint">Changes save automatically</span>
      </div>
    </Card>
  )
}
