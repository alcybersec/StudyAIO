import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Plus, Trash2 } from 'lucide-react'
import { useDeleteChatSession } from '../../hooks/useApi'
import { Button } from '../ui/Button'
import { toastMutationError } from '../../lib/toast'
import { DeleteChatModal } from './DeleteChatModal'
import type { ChatSession } from '../../types'

interface SessionRailProps {
  sessions: ChatSession[]
  selectedId: string
  onSelect: (id: string) => void
  onNewQuestion: () => void
  isCreating: boolean
}

function formatSessionDate(dateStr: string): string {
  const date = new Date(dateStr)
  const diffDays = Math.floor((Date.now() - date.getTime()) / (1000 * 60 * 60 * 24))
  if (diffDays === 0) return 'today'
  if (diffDays === 1) return 'yesterday'
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function SessionItem({
  session,
  isSelected,
  onSelect,
  onDeleted,
}: {
  session: ChatSession
  isSelected: boolean
  onSelect: () => void
  onDeleted: () => void
}) {
  const { t } = useTranslation()

  const [confirmOpen, setConfirmOpen] = useState(false)
  const deleteSession = useDeleteChatSession()

  const handleConfirm = () => {
    deleteSession.mutate(session.id, {
      onSuccess: () => {
        setConfirmOpen(false)
        onDeleted()
      },
      onError: (err) => toastMutationError(err, handleConfirm),
    })
  }

  // The row is a plain container: selecting and deleting are two sibling
  // buttons (a focusable control must not nest another — axe nested-interactive).
  return (
    <div
      className={`group w-full flex items-start gap-2 rounded-lg transition-colors ${
        isSelected ? 'bg-surface-2' : 'hover:bg-surface-2'
      }`}
    >
      <button
        type="button"
        onClick={onSelect}
        aria-current={isSelected ? 'true' : undefined}
        className="flex-1 min-w-0 text-left pl-2.5 py-2 min-h-11 rounded-lg cursor-pointer"
      >
        <span className={`block text-[13px] truncate ${isSelected ? 'text-text font-medium' : 'text-text-muted'}`}>
          {session.title || t('New question')}
        </span>
        <span className="block text-[10px] text-text-faint font-mono mt-0.5">
          {t('{{date}} · {{count}} msgs', { date: formatSessionDate(session.updated_at), count: session.message_count })}
        </span>
      </button>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation()
          setConfirmOpen(true)
        }}
        aria-label={t('Delete conversation')}
        aria-haspopup="dialog"
        className="shrink-0 flex items-center justify-center min-h-11 min-w-11 rounded-md text-text-faint hover:text-red-fg cursor-pointer transition-opacity opacity-100 lg:opacity-0 lg:group-hover:opacity-100 focus-visible:opacity-100"
      >
        <Trash2 size={14} aria-hidden />
      </button>
      <DeleteChatModal
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        session={session}
        onConfirm={handleConfirm}
        pending={deleteSession.isPending}
      />
    </div>
  )
}

export function SessionRail({ sessions, selectedId, onSelect, onNewQuestion, isCreating }: SessionRailProps) {
  const { t } = useTranslation()

  return (
    <div className="flex flex-col h-full bg-surface-1">
      <div className="p-3">
        <Button
          variant="secondary"
          size="sm"
          className="w-full"
          onClick={onNewQuestion}
          loading={isCreating}
        >
          {!isCreating && <Plus size={13} aria-hidden />} {t('New question')}
        </Button>
      </div>
      <div className="px-3 pb-2 text-[10px] font-mono uppercase tracking-[0.12em] text-text-faint">
        {t('Sessions')}
      </div>
      <div className="flex-1 overflow-y-auto px-2 pb-3 space-y-0.5">
        {sessions.length === 0 ? (
          <p className="text-sm text-text-muted text-center py-8">{t('No conversations yet')}</p>
        ) : (
          sessions.map((session) => (
            <SessionItem
              key={session.id}
              session={session}
              isSelected={session.id === selectedId}
              onSelect={() => onSelect(session.id)}
              onDeleted={() => {
                if (session.id === selectedId) {
                  const remaining = sessions.filter((s) => s.id !== session.id)
                  if (remaining.length > 0) onSelect(remaining[0].id)
                }
              }}
            />
          ))
        )}
      </div>
    </div>
  )
}
