import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'

interface UseShortcutsOptions {
  onOpenPalette: () => void
  onOpenOverlay: () => void
}

/** Milliseconds the "g" prefix stays armed for two-key sequences. */
const SEQUENCE_TIMEOUT_MS = 1000

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  if (target.isContentEditable) return true
  const tag = target.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT'
}

function isDialogOpen(): boolean {
  return document.querySelector('[role="dialog"][data-state="open"]') !== null
}

/**
 * Global keyboard shortcuts:
 * - ⌘K / Ctrl+K — command palette (works everywhere, even in inputs/dialogs)
 * - S — start study session (/study), U — upload (/upload), ? — shortcut overlay
 * - g h / g s — go home / go study (two-key sequences)
 *
 * Single-key shortcuts never fire while typing in an input, textarea,
 * select or contenteditable, or while any Radix dialog is open.
 */
export function useShortcuts({ onOpenPalette, onOpenOverlay }: UseShortcutsOptions): void {
  const navigate = useNavigate()
  const pendingG = useRef<number | null>(null)

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const key = event.key

      // ⌘K / Ctrl+K — always available
      if ((event.metaKey || event.ctrlKey) && key.toLowerCase() === 'k') {
        event.preventDefault()
        onOpenPalette()
        return
      }

      // Everything below is a single-key shortcut: guard it.
      if (event.metaKey || event.ctrlKey || event.altKey) return
      if (isEditableTarget(event.target)) return
      if (isDialogOpen()) return

      // Two-key "g" sequences
      if (pendingG.current !== null && Date.now() - pendingG.current < SEQUENCE_TIMEOUT_MS) {
        pendingG.current = null
        if (key === 'h') {
          event.preventDefault()
          navigate('/')
          return
        }
        if (key === 's') {
          event.preventDefault()
          navigate('/study')
          return
        }
        // fall through: unrecognised second key cancels the sequence
      }

      switch (key) {
        case 'g':
          pendingG.current = Date.now()
          return
        case 's':
        case 'S':
          event.preventDefault()
          navigate('/study')
          return
        case 'u':
        case 'U':
          event.preventDefault()
          navigate('/upload')
          return
        case '?':
          event.preventDefault()
          onOpenOverlay()
          return
        default:
          return
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [navigate, onOpenPalette, onOpenOverlay])
}
