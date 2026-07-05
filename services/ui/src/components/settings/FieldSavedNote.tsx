import { Check } from 'lucide-react'

interface FieldSavedNoteProps {
  show: boolean
}

/** Sage "saved" note shown next to a field label after a successful autosave. */
export function FieldSavedNote({ show }: FieldSavedNoteProps) {
  if (!show) return null
  return (
    <span className="inline-flex items-center gap-1 text-sage-fg text-[11px]" role="status">
      <Check size={11} aria-hidden /> saved
    </span>
  )
}
