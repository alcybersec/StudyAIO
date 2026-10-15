import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button, Modal, Textarea } from '../ui'
import { useCreateFlashcard, useUpdateFlashcard } from '../../hooks/useApi'
import { studyItemErrorMessage, validateFlashcard, type FieldErrors } from '../../lib/studyItems'
import type { Flashcard } from '../../types'

interface FlashcardEditorProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  courseCode: string
  week: number
  /** Present when editing; absent when adding. */
  card?: Flashcard
  /** Called with the saved card (an edit comes back under a new id). */
  onSaved?: (card: Flashcard) => void
}

function EditorForm({ onOpenChange, courseCode, week, card, onSaved }: Omit<FlashcardEditorProps, 'open'>) {
  const { t } = useTranslation()
  const create = useCreateFlashcard()
  const update = useUpdateFlashcard()
  const [front, setFront] = useState(card?.front ?? '')
  const [back, setBack] = useState(card?.back ?? '')
  const [errors, setErrors] = useState<FieldErrors<'front' | 'back'>>({})
  const [serverError, setServerError] = useState<string>()
  const pending = create.isPending || update.isPending

  function submit(e: React.FormEvent) {
    e.preventDefault()
    const found = validateFlashcard({ front, back })
    setErrors(found)
    setServerError(undefined)
    if (Object.keys(found).length > 0) return
    const done = (saved: Flashcard) => {
      onSaved?.(saved)
      onOpenChange(false)
    }
    const fail = (err: unknown) => setServerError(studyItemErrorMessage(err))
    if (card) {
      update.mutate({ id: card.id, body: { front: front.trim(), back: back.trim() } }, { onSuccess: done, onError: fail })
    } else {
      create.mutate(
        { course_code: courseCode, week, front: front.trim(), back: back.trim() },
        { onSuccess: done, onError: fail },
      )
    }
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-3">
      <Textarea label={t('Front')} value={front} onChange={(e) => setFront(e.target.value)} error={errors.front} rows={3} autoFocus />
      <Textarea label={t('Back')} value={back} onChange={(e) => setBack(e.target.value)} error={errors.back} rows={4} />
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
          {card ? t('Save changes') : t('Add card')}
        </Button>
      </div>
    </form>
  )
}

/** Modal form to add a flashcard to a week, or edit one (an edit becomes a new copy; the original is archived). */
export function FlashcardEditor({ open, onOpenChange, ...rest }: FlashcardEditorProps) {
  const { t } = useTranslation()
  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={rest.card ? t('Edit flashcard') : t('Add flashcard')}
      description={rest.card ? t('Your review progress carries over.') : undefined}
    >
      <EditorForm onOpenChange={onOpenChange} {...rest} />
    </Modal>
  )
}
