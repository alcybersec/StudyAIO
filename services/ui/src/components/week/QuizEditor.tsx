import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Plus, Trash2 } from 'lucide-react'
import { Button, Input, Modal, Textarea } from '../ui'
import { useCreateQuizQuestion, useUpdateQuizQuestion } from '../../hooks/useApi'
import {
  MAX_OPTIONS,
  MIN_OPTIONS,
  draftFromQuestion,
  quizPayload,
  studyItemErrorMessage,
  validateQuiz,
  type FieldErrors,
  type QuizDraft,
  type QuizField,
} from '../../lib/studyItems'
import type { QuizQuestion } from '../../types'

interface QuizEditorProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  courseCode: string
  week: number
  /** Present when editing; absent when adding. */
  question?: QuizQuestion
  onSaved?: (question: QuizQuestion) => void
}

const BLANK: QuizDraft = {
  type: 'multiple_choice',
  question: '',
  options: ['', ''],
  correctIndex: null,
  answer: '',
  explanation: '',
}

function OptionsEditor({
  draft,
  setDraft,
  errors,
}: {
  draft: QuizDraft
  setDraft: (d: QuizDraft) => void
  errors: FieldErrors<QuizField>
}) {
  const { t } = useTranslation()
  const setOption = (i: number, value: string) =>
    setDraft({ ...draft, options: draft.options.map((o, j) => (j === i ? value : o)) })
  const removeOption = (i: number) =>
    setDraft({
      ...draft,
      options: draft.options.filter((_, j) => j !== i),
      correctIndex:
        draft.correctIndex === null || draft.correctIndex === i
          ? null
          : draft.correctIndex > i
            ? draft.correctIndex - 1
            : draft.correctIndex,
    })

  return (
    <fieldset className="space-y-2">
      <legend className="text-xs font-medium text-text-muted mb-1.5">{t('Options (select the correct one)')}</legend>
      {draft.options.map((opt, i) => (
        <div key={i} className="flex items-center gap-2">
          <input
            type="radio"
            name="correct-option"
            checked={draft.correctIndex === i}
            onChange={() => setDraft({ ...draft, correctIndex: i })}
            aria-label={t('Option {{n}} is correct', { n: i + 1 })}
            className="w-5 h-5 shrink-0 accent-[var(--color-sage)]"
          />
          <Input
            className="flex-1"
            value={opt}
            onChange={(e) => setOption(i, e.target.value)}
            aria-label={t('Option {{n}}', { n: i + 1 })}
          />
          <button
            type="button"
            onClick={() => removeOption(i)}
            disabled={draft.options.length <= MIN_OPTIONS}
            aria-label={t('Remove option {{n}}', { n: i + 1 })}
            className="min-w-11 min-h-11 flex items-center justify-center rounded-md text-text-faint hover:text-red-fg disabled:opacity-40 cursor-pointer focus-visible:outline-2 focus-visible:outline-peri"
          >
            <Trash2 size={14} aria-hidden />
          </button>
        </div>
      ))}
      {draft.options.length < MAX_OPTIONS && (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="min-h-11"
          onClick={() => setDraft({ ...draft, options: [...draft.options, ''] })}
        >
          <Plus size={12} aria-hidden /> {t('Add option')}
        </Button>
      )}
      {(errors.options || errors.correct) && (
        <p role="alert" className="text-xs text-red-fg">
          {errors.options ?? errors.correct}
        </p>
      )}
    </fieldset>
  )
}

function EditorForm({ onOpenChange, courseCode, week, question, onSaved }: Omit<QuizEditorProps, 'open'>) {
  const { t } = useTranslation()
  const create = useCreateQuizQuestion()
  const update = useUpdateQuizQuestion()
  const [draft, setDraft] = useState<QuizDraft>(question ? draftFromQuestion(question) : BLANK)
  const [errors, setErrors] = useState<FieldErrors<QuizField>>({})
  const [serverError, setServerError] = useState<string>()
  const pending = create.isPending || update.isPending
  const mc = draft.type === 'multiple_choice'

  function submit(e: React.FormEvent) {
    e.preventDefault()
    const found = validateQuiz(draft)
    setErrors(found)
    setServerError(undefined)
    if (Object.keys(found).length > 0) return
    const done = (saved: QuizQuestion) => {
      onSaved?.(saved)
      onOpenChange(false)
    }
    const fail = (err: unknown) => setServerError(studyItemErrorMessage(err))
    const payload = quizPayload(draft)
    if (question) {
      const patch = {
        question: payload.question,
        options: payload.options,
        correct_answer: payload.correct_answer,
        explanation: payload.explanation,
      }
      update.mutate({ id: question.id, body: patch }, { onSuccess: done, onError: fail })
    } else {
      create.mutate({ course_code: courseCode, week, ...payload }, { onSuccess: done, onError: fail })
    }
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-3 max-h-[70vh] overflow-y-auto pr-1">
      {!question && (
        <div role="radiogroup" aria-label={t('Question type')} className="flex gap-2">
          {(['multiple_choice', 'short_answer'] as const).map((type) => (
            <button
              key={type}
              type="button"
              role="radio"
              aria-checked={draft.type === type}
              onClick={() => setDraft({ ...draft, type })}
              className={`px-4 py-2.5 min-h-11 rounded-full text-xs font-medium cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-peri ${
                draft.type === type ? 'bg-peri-soft text-peri-fg' : 'bg-surface-2 text-text-muted hover:text-text'
              }`}
            >
              {type === 'multiple_choice' ? t('Multiple choice') : t('Short answer')}
            </button>
          ))}
        </div>
      )}
      <Textarea
        label={t('Question')}
        value={draft.question}
        onChange={(e) => setDraft({ ...draft, question: e.target.value })}
        error={errors.question}
        rows={3}
        autoFocus
      />
      {mc ? (
        <OptionsEditor draft={draft} setDraft={setDraft} errors={errors} />
      ) : (
        <Textarea
          label={t('Model answer')}
          value={draft.answer}
          onChange={(e) => setDraft({ ...draft, answer: e.target.value })}
          error={errors.answer}
          rows={3}
        />
      )}
      <Textarea
        label={t('Explanation (optional)')}
        value={draft.explanation}
        onChange={(e) => setDraft({ ...draft, explanation: e.target.value })}
        error={errors.explanation}
        rows={2}
      />
      {serverError && (
        <p role="alert" className="text-xs text-red-fg">
          {serverError}
        </p>
      )}
      <div className="flex flex-wrap justify-end gap-2">
        <Button type="button" variant="secondary" size="sm" className="min-h-11" onClick={() => onOpenChange(false)} disabled={pending}>
          {t('Cancel')}
        </Button>
        <Button type="submit" size="sm" className="min-h-11" loading={pending}>
          {question ? t('Save changes') : t('Add question')}
        </Button>
      </div>
    </form>
  )
}

/** Modal form to add a quiz question to a week, or edit one (an edit becomes a new copy; the original is archived). */
export function QuizEditor({ open, onOpenChange, ...rest }: QuizEditorProps) {
  const { t } = useTranslation()
  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={rest.question ? t('Edit question') : t('Add question')}
    >
      <EditorForm onOpenChange={onOpenChange} {...rest} />
    </Modal>
  )
}
