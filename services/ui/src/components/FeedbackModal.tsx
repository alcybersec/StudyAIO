import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import { toast } from 'sonner'
import { Button, Modal } from './ui'
import { useSubmitFeedback } from '../hooks/useApi'
import type { FeedbackKind } from '../types'

/** Mirrors `FEEDBACK_KINDS` on the server. */
const KINDS: { value: FeedbackKind; label: string; placeholder: string }[] = [
  {
    value: 'bug',
    label: 'Something broke',
    placeholder: 'What did you do, and what happened instead?',
  },
  {
    value: 'confusing',
    label: 'Something confused me',
    placeholder: 'What did you expect to happen here?',
  },
  {
    value: 'idea',
    label: 'An idea',
    placeholder: 'What would you want instead?',
  },
]

/** Mirrors `MAX_MESSAGE_LENGTH` in `feedback_service`. */
const MAX_LENGTH = 4000

interface FeedbackModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

/**
 * Say something about the app from inside it.
 *
 * Sentry catches what crashes and the beta funnel shows that someone stopped
 * after their first upload. Neither can tell you that a label was misleading,
 * which is the kind of thing that decides whether a tester comes back.
 *
 * The current route and the build's commit SHA are attached automatically. A
 * report that says "the summary looked empty" is unactionable; the same report
 * with a page and a commit is reproducible.
 */
export function FeedbackModal({ open, onOpenChange }: FeedbackModalProps) {
  const location = useLocation()
  const [kind, setKind] = useState<FeedbackKind>('bug')
  const [message, setMessage] = useState('')
  const [error, setError] = useState<string | null>(null)
  const submit = useSubmitFeedback()

  const active = KINDS.find((k) => k.value === kind) ?? KINDS[0]
  const trimmed = message.trim()
  const canSubmit = trimmed.length > 0 && trimmed.length <= MAX_LENGTH && !submit.isPending

  const close = () => {
    onOpenChange(false)
    setMessage('')
    setError(null)
    setKind('bug')
  }

  const send = () => {
    setError(null)
    submit.mutate(
      {
        kind,
        message: trimmed,
        route: location.pathname,
        app_version: import.meta.env.VITE_SENTRY_RELEASE || null,
      },
      {
        onSuccess: () => {
          toast.success('Thank you — that went straight to the maintainer.')
          close()
        },
        onError: (err: unknown) => {
          // Kept in the modal rather than a toast: the text is still in the box,
          // and closing it over a failed send would lose what they wrote.
          setError(
            err instanceof Error && err.message
              ? err.message
              : "Couldn't send that. Your text is still here — try again.",
          )
        },
      },
    )
  }

  return (
    <Modal
      open={open}
      onOpenChange={(next) => (next ? onOpenChange(true) : close())}
      title="Send feedback"
    >
      <div className="space-y-3">
        <div className="flex flex-wrap gap-1.5">
          {KINDS.map((k) => (
            <button
              key={k.value}
              type="button"
              aria-pressed={kind === k.value}
              onClick={() => setKind(k.value)}
              className={
                kind === k.value
                  ? 'px-2.5 py-1 rounded-full text-xs bg-sage-soft text-text border border-sage/40'
                  : 'px-2.5 py-1 rounded-full text-xs bg-surface-2 text-text-muted border border-border'
              }
            >
              {k.label}
            </button>
          ))}
        </div>

        <div>
          <label htmlFor="feedback-message" className="sr-only">
            Your feedback
          </label>
          <textarea
            id="feedback-message"
            rows={5}
            autoFocus
            value={message}
            maxLength={MAX_LENGTH}
            placeholder={active.placeholder}
            onChange={(e) => setMessage(e.target.value)}
            className="w-full rounded-lg bg-surface-2 border border-border px-3 py-2 text-xs text-text placeholder:text-text-faint"
          />
          <p className="mt-1 text-[11px] text-text-faint">
            The page you are on is included so this can be reproduced. Nothing else is
            collected.
          </p>
        </div>

        {error && (
          <p role="alert" className="text-xs text-red-fg">
            {error}
          </p>
        )}

        <div className="flex justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={close}>
            Cancel
          </Button>
          <Button size="sm" disabled={!canSubmit} onClick={send}>
            {submit.isPending ? 'Sending…' : 'Send'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}
