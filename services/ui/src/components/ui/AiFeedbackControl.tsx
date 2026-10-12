import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ThumbsDown, ThumbsUp } from 'lucide-react'
import { useAiFeedback } from '../../hooks/useAiFeedback'
import type { AIFeedbackReason, AIFeedbackTargetType } from '../../types'

const COMMENT_MAX = 1000

interface AiFeedbackControlProps {
  targetType: AIFeedbackTargetType
  targetId: string
  /** Every id shown in this view, so their votes load in one request. Defaults to just this item. */
  batchIds?: string[]
  className?: string
}

const buttonBase =
  'inline-flex items-center justify-center min-h-[44px] min-w-[44px] sm:min-h-8 sm:min-w-8 rounded-md border text-text-muted cursor-pointer transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-peri'

/** Compact thumbs up/down on one piece of AI output, with a reason picker on thumbs down. */
export function AiFeedbackControl({ targetType, targetId, batchIds, className = '' }: AiFeedbackControlProps) {
  const { t } = useTranslation()
  const groupId = useId()

  const { votes, vote } = useAiFeedback(targetType, batchIds ?? [targetId])
  const current = votes.get(targetId)
  const [picking, setPicking] = useState(false)
  const [reason, setReason] = useState<AIFeedbackReason | ''>('')
  const [comment, setComment] = useState('')

  const reasons: { value: AIFeedbackReason; label: string }[] = [
    { value: 'inaccurate', label: t('Inaccurate') },
    { value: 'not_in_my_lectures', label: t('Not in my lectures') },
    { value: 'unclear', label: t('Unclear') },
    { value: 'wrong_format', label: t('Wrong format') },
    { value: 'other', label: t('Other') },
  ]

  const up = current?.rating === 1
  const down = current?.rating === -1

  function onUp() {
    setPicking(false)
    vote(targetId, up ? null : { rating: 1 })
  }

  function onDown() {
    if (down) {
      setPicking(false)
      vote(targetId, null)
    } else {
      setPicking((p) => !p)
    }
  }

  function submitDown() {
    vote(targetId, {
      rating: -1,
      ...(reason ? { reason } : {}),
      ...(comment.trim() ? { comment: comment.trim().slice(0, COMMENT_MAX) } : {}),
    })
    setPicking(false)
    setReason('')
    setComment('')
  }

  return (
    <div className={`inline-flex flex-col gap-2 ${className}`}>
      <div role="group" aria-label={t('Rate this AI answer')} className="inline-flex items-center gap-1">
        <button
          type="button"
          aria-pressed={up}
          aria-label={t('Helpful')}
          title={t('Helpful')}
          onClick={onUp}
          className={`${buttonBase} ${up ? 'bg-sage-soft border-sage/40 text-sage-fg' : 'border-border hover:bg-surface-2'}`}
        >
          <ThumbsUp size={14} aria-hidden />
        </button>
        <button
          type="button"
          aria-pressed={down}
          aria-label={t('Not helpful')}
          title={t('Not helpful')}
          aria-expanded={picking}
          onClick={onDown}
          className={`${buttonBase} ${down ? 'bg-red-soft border-red/40 text-red-fg' : 'border-border hover:bg-surface-2'}`}
        >
          <ThumbsDown size={14} aria-hidden />
        </button>
      </div>

      {picking && (
        <fieldset className="w-full max-w-sm rounded-lg border border-border bg-surface-1 p-3 space-y-2 text-left">
          <legend className="px-1 text-xs font-medium text-text">{t("What wasn't right?")}</legend>
          <div className="flex flex-wrap gap-1.5">
            {reasons.map((r) => (
              <label
                key={r.value}
                className={`inline-flex items-center min-h-[44px] sm:min-h-8 px-3 rounded-full border text-xs cursor-pointer has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-peri ${
                  reason === r.value ? 'bg-peri-soft border-peri text-peri-fg' : 'border-border text-text-muted'
                }`}
              >
                <input
                  type="radio"
                  name={`${groupId}-reason`}
                  value={r.value}
                  checked={reason === r.value}
                  onChange={() => setReason(r.value)}
                  className="sr-only"
                />
                {r.label}
              </label>
            ))}
          </div>
          <label className="block text-xs text-text-muted">
            {t('Comment (optional)')}
            <textarea
              value={comment}
              maxLength={COMMENT_MAX}
              rows={2}
              onChange={(e) => setComment(e.target.value)}
              className="mt-1 w-full rounded-md border border-border bg-surface-0 p-2 text-sm text-text focus:outline-none focus:border-peri"
            />
          </label>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setPicking(false)}
              className="min-h-[44px] sm:min-h-8 px-3 rounded-md text-xs text-text-muted hover:bg-surface-2 cursor-pointer focus-visible:outline-2 focus-visible:outline-peri"
            >
              {t('Cancel')}
            </button>
            <button
              type="button"
              onClick={submitDown}
              className="min-h-[44px] sm:min-h-8 px-3 rounded-md text-xs font-medium bg-sage text-on-accent hover:bg-sage-hover cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-peri"
            >
              {t('Send feedback')}
            </button>
          </div>
        </fieldset>
      )}
    </div>
  )
}
