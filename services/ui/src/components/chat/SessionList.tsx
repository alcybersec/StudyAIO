import { useState } from 'react'
import { useDeleteChatSession } from '../../hooks/useApi'
import type { ChatSession } from '../../types'

interface SessionListProps {
  sessions: ChatSession[]
  selectedId: string
  onSelect: (id: string) => void
  onNewChat: () => void
  isCreating: boolean
}

function formatSessionDate(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays === 0) return 'Today'
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function SessionItem({ session, isSelected, onSelect, onDeleted }: {
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
    <button
      onClick={onSelect}
      className={`group w-full flex items-start gap-2 px-3 py-2.5 rounded-lg text-left text-sm transition-colors min-h-[44px] ${
        isSelected
          ? 'bg-primary/10 text-primary'
          : 'text-text hover:bg-surface-alt'
      }`}
    >
      <div className="flex-1 min-w-0">
        <p className="font-medium truncate">{session.title || 'New Chat'}</p>
        <p className="text-xs text-text-muted mt-0.5">
          {session.message_count} msg{session.message_count !== 1 ? 's' : ''} &middot; {formatSessionDate(session.updated_at)}
        </p>
      </div>
      <button
        onClick={handleDelete}
        disabled={deleteSession.isPending}
        className={`shrink-0 mt-0.5 p-1 rounded opacity-0 group-hover:opacity-100 transition-opacity ${
          confirmDelete
            ? 'text-danger opacity-100'
            : 'text-text-muted hover:text-danger'
        }`}
        title={confirmDelete ? 'Click again to confirm delete' : 'Delete conversation'}
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
        </svg>
      </button>
    </button>
  )
}

export function SessionList({ sessions, selectedId, onSelect, onNewChat, isCreating }: SessionListProps) {
  return (
    <div className="flex flex-col h-full">
      {/* New chat button */}
      <div className="p-3 border-b border-border">
        <button
          onClick={onNewChat}
          disabled={isCreating}
          className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg bg-primary text-white text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity min-h-[44px]"
        >
          {isCreating ? (
            <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
          ) : (
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
          )}
          <span>New Chat</span>
        </button>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
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
