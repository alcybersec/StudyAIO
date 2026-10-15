import { useTranslation } from 'react-i18next'
import { AlertTriangle } from 'lucide-react'
import { Button, Modal } from '../ui'

interface DeleteItemModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  /** The text of the item being removed, so the user sees what they are confirming. */
  preview: string
  onConfirm: () => void
  pending: boolean
  error?: string
}

/** Confirmation before a card or question is removed. Cancel holds initial focus. */
export function DeleteItemModal({ open, onOpenChange, title, preview, onConfirm, pending, error }: DeleteItemModalProps) {
  const { t } = useTranslation()

  return (
    <Modal
      open={open}
      onOpenChange={(next) => {
        if (!pending) onOpenChange(next)
      }}
      title={
        <span className="flex items-center gap-2.5">
          <span className="w-8 h-8 rounded-lg bg-red-soft text-red-fg flex items-center justify-center shrink-0">
            <AlertTriangle size={15} aria-hidden />
          </span>
          {title}
        </span>
      }
      description={t('It leaves your study sets. Your review history is kept.')}
      className="border-red/30"
    >
      <p className="text-sm text-text font-medium break-words line-clamp-4 mb-4">{preview}</p>
      {error && (
        <p role="alert" className="text-xs text-red-fg mb-3">
          {error}
        </p>
      )}
      <div className="flex flex-wrap justify-end gap-2">
        <Button
          variant="secondary"
          size="sm"
          className="min-h-11 min-w-11"
          autoFocus
          onClick={() => onOpenChange(false)}
          disabled={pending}
        >
          {t('Cancel')}
        </Button>
        <Button variant="danger" size="sm" className="min-h-11 min-w-11" loading={pending} onClick={onConfirm}>
          {t('Delete')}
        </Button>
      </div>
    </Modal>
  )
}
