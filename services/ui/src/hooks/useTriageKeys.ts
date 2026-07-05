import { useEffect } from 'react'

export interface TriageKeyHandlers {
  /** Move the focused row down (+1) or up (-1). */
  onMove: (delta: 1 | -1) => void
  onApprove: () => void
  onEdit: () => void
  onDismiss: () => void
  /** Close an open inline editor (Escape). */
  onCancelEdit: () => void
}

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  if (target.isContentEditable) return true
  const tag = target.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT'
}

/**
 * List-triage keyboard shortcuts: j/k move the focused row, a approves,
 * e edits, d dismisses. While an inline editor is open only Escape (cancel)
 * is handled — everything else is ignored so typing can't trigger actions.
 * Shortcuts never fire from inputs, textareas, selects or contenteditable,
 * nor with a modifier key held.
 */
export function useTriageKeys(
  enabled: boolean,
  editing: boolean,
  handlers: TriageKeyHandlers,
): void {
  useEffect(() => {
    if (!enabled) return

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.metaKey || event.ctrlKey || event.altKey) return
      if (isEditableTarget(event.target)) return

      if (editing) {
        if (event.key === 'Escape') {
          event.preventDefault()
          handlers.onCancelEdit()
        }
        return
      }

      switch (event.key) {
        case 'j':
          event.preventDefault()
          handlers.onMove(1)
          return
        case 'k':
          event.preventDefault()
          handlers.onMove(-1)
          return
        case 'a':
          event.preventDefault()
          handlers.onApprove()
          return
        case 'e':
          event.preventDefault()
          handlers.onEdit()
          return
        case 'd':
          event.preventDefault()
          handlers.onDismiss()
          return
        default:
          return
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [enabled, editing, handlers])
}
