import { useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { useDeleteChatSession } from '../../hooks/useApi'
import { Button } from '../ui/Button'
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
  const [confirmDelete, setConfirmDelete] = useState(false)
  const deleteSession = useDeleteChatSession()

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirmDelete) {
      setConfirmDelete(true)
      setTimeout(() => setConfirmDelete(false), 3000)
      return
    }
    deleteSession.mutate(session.id, { onSuccess: onDeleted })
  }

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onSelect()
        }
      }}
      className={`group w-full flex items-start gap-2 text-left px-2.5 py-2 rounded-lg cursor-pointer transition-colors ${
        isSelected ? 'bg-surface-2' : 'hover:bg-surface-2'
      }`}
    >
      <div className="flex-1 min-w-0">
        <div className={`text-[13px] truncate ${isSelected ? 'text-text font-medium' : 'text-text-muted'}`}>
          {session.title || 'New question'}
        </div>
        <div className="text-[10px] text-text-faint font-mono mt-0.5">
          {formatSessionDate(session.updated_at)} · {session.message_count} msgs
        </div>
      </div>
      <button
        type="button"
        onClick={handleDelete}
        disabled={deleteSession.isPending}
        aria-label={confirmDelete ? 'Confirm delete conversation' : 'Delete conversation'}
        title={confirmDelete ? 'Click again to confirm' : 'Delete conversation'}
        className={`shrink-0 mt-0.5 p-1 rounded-md transition-opacity cursor-pointer ${
          confirmDelete
            ? 'text-red-fg opacity-100'
            : 'text-text-faint hover:text-red-fg opacity-0 group-hover:opacity-100 focus-visible:opacity-100'
        }`}
      >
        <Trash2 size={13} aria-hidden />
      </button>
    </div>
  )
}

export function SessionRail({ sessions, selectedId, onSelect, onNewQuestion, isCreating }: SessionRailProps) {
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
          {!isCreating && <Plus size={13} aria-hidden />} New question
        </Button>
      </div>
      <div className="px-3 pb-2 text-[10px] font-mono uppercase tracking-[0.12em] text-text-faint">
        Sessions
      </div>
      <div className="flex-1 overflow-y-auto px-2 pb-3 space-y-0.5">
        {sessions.length === 0 ? (
          <p className="text-sm text-text-muted text-center py-8">No conversations yet</p>
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
