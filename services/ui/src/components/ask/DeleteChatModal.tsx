import { useTranslation } from 'react-i18next'
import { AlertTriangle } from 'lucide-react'
import { Button, Modal } from '../ui'
import type { ChatSession } from '../../types'

interface DeleteChatModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  session: ChatSession
  onConfirm: () => void
  pending: boolean
}

/**
 * Explicit confirmation before a conversation is deleted. Cancel holds initial
 * focus so a stray Enter/Space (or a double-tap that lands on the dialog)
 * never destroys anything.
 */
export function DeleteChatModal({ open, onOpenChange, session, onConfirm, pending }: DeleteChatModalProps) {
  const { t } = useTranslation()
  const name = session.title || t('New question')

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
          {t('Delete this conversation?')}
        </span>
      }
      description={t("This can't be undone.")}
      className="border-red/30"
    >
      <p className="text-sm text-text font-medium break-words">{name}</p>
      <p className="text-xs text-text-muted mt-1 mb-4">
        {t('{{count}} messages will be permanently deleted', { count: session.message_count })}
      </p>
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
        <Button
          variant="danger"
          size="sm"
          className="min-h-11 min-w-11"
          loading={pending}
          onClick={onConfirm}
        >
          {t('Delete')}
        </Button>
      </div>
    </Modal>
  )
}
